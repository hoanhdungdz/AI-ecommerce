"""
RAG Chatbot Consultant - AIConsultant Class
Sử dụng ChromaDB (Vector Database) + Sentence-Transformers (Local Embedding, miễn phí)
Tích hợp vào hệ thống Django TechShop thông qua FastAPI.
"""
import os
import re
import json
import logging
import unicodedata
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError
from chromadb import PersistentClient
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)


class AIConsultant:
    """
    AI Consultant sử dụng RAG (Retrieval-Augmented Generation):
    1. Vector Database: ChromaDB lưu trữ Knowledge Base từ mô tả sản phẩm
    2. Embedding: sentence-transformers (chạy local, miễn phí - không cần API key)
    3. Retrieval: Similarity Search tìm sản phẩm liên quan
    4. Generation: Tạo câu trả lời tư vấn dựa trên context
    """

    def __init__(self, persist_directory="./chroma_db", collection_name="techshop_products"):
        logger.info("Khởi tạo AIConsultant với Sentence-Transformers (local)...")

        # Sử dụng Sentence-Transformers Embedding (chạy local, miễn phí)
        # Model 'all-MiniLM-L6-v2' nhẹ (~80MB), nhanh, hỗ trợ đa ngôn ngữ cơ bản
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

        # Khởi tạo ChromaDB PersistentClient
        self.chroma_client = PersistentClient(path=persist_directory)

        # Tạo hoặc lấy Collection
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"}  # Sử dụng cosine similarity
        )

        # Mặc định chỉ tư vấn catalog chính trên web: Laptop + Mobile.
        primary_cats = os.getenv("AI_PRIMARY_CATEGORIES", "Laptop,Mobile")
        self.primary_categories = {
            self._normalize_category(c) for c in primary_cats.split(",") if c.strip()
        }

        # Retrieval safety config
        self.retrieval_min_k = 5
        self.retrieval_max_k = 10
        # Có thể tăng lên 0.7 trong production nếu embedding/corpus ổn định hơn.
        self.safe_similarity_threshold = float(
            os.getenv("AI_SAFE_SIMILARITY_THRESHOLD", "0.5")
        )
        self.live_search_url = os.getenv(
            "AI_LIVE_SEARCH_URL",
            "http://api-gateway:8000/api/customers/search/"
        ).rstrip("/") + "/"

        # System prompt để kiểm soát hành vi tư vấn (dùng cho lớp generate/LLM nếu mở rộng).
        self.system_prompt = (
            "Bạn là tư vấn viên TechShop.\n"
            "1. Tuyệt đối không giới thiệu sản phẩm nằm ngoài [Context] được cung cấp.\n"
            "2. Nếu [Context] trống, hãy nói: 'Rất tiếc, TechShop hiện không có sản phẩm nào thỏa mãn đúng yêu cầu của bạn'.\n"
            "3. Nếu khách hỏi sản phẩm A mà trong kho chỉ có sản phẩm B, phải khẳng định không có A trước khi gợi ý B.\n"
            "4. Tuyệt đối không nhầm lẫn giữa Laptop, Mobile và Smartwatch."
        )

        logger.info(f"✅ AIConsultant sẵn sàng. Collection '{collection_name}' "
                     f"có {self.collection.count()} documents.")

    @staticmethod
    def _normalize_similarity(distance):
        """Chuyển distance về similarity nằm trong [0, 1] để hiển thị ổn định."""
        try:
            d = max(0.0, float(distance))
        except (TypeError, ValueError):
            return 0.0
        return 1.0 / (1.0 + d)

    @staticmethod
    def _parse_price_to_vnd(value):
        """Chuyển giá metadata về số VND (float)."""
        if value is None:
            return None
        try:
            return float(str(value).replace(",", "").strip())
        except (TypeError, ValueError):
            pass

        text = str(value)
        m = re.search(r"(\d+(?:\.\d+)?)", text)
        if not m:
            return None
        try:
            return float(m.group(1))
        except ValueError:
            return None

    @staticmethod
    def _strip_accents(text):
        if not text:
            return ""
        # NFD không tách ký tự 'đ', nên chuẩn hoá thủ công trước để matching tiếng Việt ổn định.
        text = str(text).replace("đ", "d").replace("Đ", "D")
        normalized = unicodedata.normalize("NFD", text)
        return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")

    def _normalize_category(self, text):
        raw = self._strip_accents((text or "").strip().lower())
        if raw in {"dien thoai", "mobile", "smartphone", "phone"}:
            return "mobile"
        if raw in {"laptop", "notebook"}:
            return "laptop"
        if raw in {"tablet", "may tinh bang"}:
            return "tablet"
        if raw in {"smartwatch", "dong ho thong minh", "watch"}:
            return "smartwatch"
        if raw in {"phu kien", "accessory", "accessories"}:
            return "accessory"
        return raw

    def _tokenize_query(self, query):
        text = self._strip_accents((query or "").lower())
        tokens = re.findall(r"\w+", text)
        stopwords = {
            "toi", "minh", "ban", "muon", "can", "tim", "kiem", "ve", "va", "cho", "cua",
            "la", "cac", "nhung", "tren", "duoi", "hon", "nho", "lon", "tung", "loai",
            "gia", "trieu", "nghin", "vnd", "san", "pham", "chi", "tiet", "ki", "ky", "ki", "ky", "more",
            "mua", "nao", "chuyen", "dung", "toi", "tam", "khoang"
        }
        return [t for t in tokens if len(t) >= 2 and t not in stopwords]

    def _is_smalltalk_query(self, query):
        """Nhận diện câu xã giao để tránh gợi ý sản phẩm sai ngữ cảnh."""
        q = self._strip_accents((query or "").lower()).strip()
        if not q:
            return True

        smalltalk_keywords = [
            "xin chao", "chao", "hello", "hi", "helo", "alo",
            "cam on", "thanks", "thank", "tam biet", "bye", "good morning", "good evening",
            "ban la ai", "ban ten gi", "tro giup"
        ]
        product_keywords = [
            "laptop", "mobile", "smartphone", "dien thoai", "tablet", "smartwatch",
            "dong ho", "accessory", "phu kien", "gia", "trieu", "duoi", "tren",
            "so sanh", "goi y", "mua", "hieu nang", "manh nhat"
        ]

        has_smalltalk = any(k in q for k in smalltalk_keywords)
        has_product = any(k in q for k in product_keywords) or bool(self._extract_category_intent(q))
        return has_smalltalk and not has_product

    def _is_laptop_performance_query(self, query):
        q = self._strip_accents((query or "").lower())
        laptop_terms = ["laptop", "notebook"]
        perf_terms = ["manh nhat", "cau hinh", "hieu nang", "performance", "gaming", "manh"]
        return any(t in q for t in laptop_terms) and any(t in q for t in perf_terms)

    def _detect_intent(self, query):
        """Phân tích ý định chính của khách hàng để quyết định cách tư vấn."""
        q = self._strip_accents((query or "").lower())
        if any(k in q for k in ["manh nhat", "tot nhat", "cao cap", "hieu nang", "cau hinh"]):
            return "best_performance"
        if any(k in q for k in ["re nhat", "gia re", "tiet kiem", "duoi", "thap nhat"]):
            return "budget"
        if any(k in q for k in ["dep", "thiet ke", "mong nhe", "sang", "premium"]):
            return "design"
        if any(k in q for k in ["phan van", "lua chon", "so sanh", "goi y", "tam", "khoang"]):
            return "comparison"
        return "balanced"

    def _determine_target_k(self, query, default_k=3):
        """Không mặc định 3; số lượng đề xuất phụ thuộc intent."""
        intent = self._detect_intent(query)
        if intent == "best_performance":
            return 2
        if intent == "comparison":
            return 3
        return min(default_k, 2)

    @staticmethod
    def _first_number(text, pattern):
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            return 0.0
        try:
            return float(m.group(1))
        except ValueError:
            return 0.0

    def _score_laptop_performance(self, doc, meta):
        text = self._strip_accents((doc or "").lower())

        cpu_score = 0.0
        cpu_patterns = [
            (r"i9[-\s]?\d+", 10.0),
            (r"ryzen\s*9", 9.5),
            (r"m3\s*pro|m3\s*max", 9.0),
            (r"i7[-\s]?\d+", 8.0),
            (r"ryzen\s*7", 7.8),
            (r"m3", 7.5),
            (r"i5[-\s]?\d+", 6.2),
            (r"ryzen\s*5", 6.0),
        ]
        for pat, score in cpu_patterns:
            if re.search(pat, text):
                cpu_score = max(cpu_score, score)

        gpu_score = 0.0
        gpu_patterns = [
            (r"rtx\s*4090", 10.0),
            (r"rtx\s*4080", 9.5),
            (r"rtx\s*4070", 8.8),
            (r"rtx\s*4060", 8.2),
            (r"rtx\s*4050", 7.4),
            (r"rtx\s*30\d\d", 7.0),
        ]
        for pat, score in gpu_patterns:
            if re.search(pat, text):
                gpu_score = max(gpu_score, score)

        ram_gb = self._first_number(text, r"ram\s*[:]?\s*(\d+(?:\.\d+)?)\s*gb")
        if ram_gb == 0:
            ram_gb = self._first_number(text, r"(\d+(?:\.\d+)?)\s*gb\s*ram")

        ssd_tb = self._first_number(text, r"ssd\s*[:]?\s*(\d+(?:\.\d+)?)\s*tb")
        if ssd_tb == 0:
            ssd_gb = self._first_number(text, r"ssd\s*[:]?\s*(\d+(?:\.\d+)?)\s*gb")
            ssd_tb = ssd_gb / 1024.0

        price_vnd = self._parse_price_to_vnd((meta or {}).get("price")) or 0.0

        # Ưu tiên cấu hình thực (CPU/GPU/RAM/SSD), giá chỉ để tie-break nhẹ.
        return (
            cpu_score * 3.2
            + gpu_score * 3.0
            + min(ram_gb, 64) * 0.12
            + min(ssd_tb, 4) * 0.9
            + price_vnd * 0.000000005
        )

    def _filter_by_similarity_threshold(self, search_results, threshold=None, query=None):
        """Giữ lại các kết quả có similarity >= ngưỡng an toàn để giảm trả lời sai ngữ cảnh."""
        if threshold is None:
            threshold = self.safe_similarity_threshold

        docs = search_results["documents"][0]
        metas = search_results["metadatas"][0]
        dists = search_results["distances"][0]
        if not docs:
            return search_results

        intents = self._extract_category_intent(query) if query else set()

        filtered_docs, filtered_meta, filtered_dist = [], [], []
        for doc, meta, dist in zip(docs, metas, dists):
            sim = self._normalize_similarity(dist)

            # Nếu user nêu rõ loại sản phẩm (vd: điện thoại/laptop),
            # cộng một phần điểm nhỏ khi category khớp để tránh loại nhầm kết quả đúng ngữ cảnh.
            if intents:
                category = self._normalize_category((meta or {}).get("category"))
                if category in intents:
                    sim += 0.08

            if sim < threshold:
                continue
            filtered_docs.append(doc)
            filtered_meta.append(meta)
            filtered_dist.append(dist)

        return {
            "documents": [filtered_docs],
            "metadatas": [filtered_meta],
            "distances": [filtered_dist],
        }

    def _extract_specs(self, doc):
        """Trích xuất nhanh thông số từ text đã vectorize (nếu có)."""
        text = doc or ""

        def pick(pattern):
            m = re.search(pattern, text, flags=re.IGNORECASE)
            return m.group(1).strip() if m else None

        specs = {
            "cpu": pick(r"CPU\s*:\s*([^,\.]+)"),
            "gpu": pick(r"GPU\s*:\s*([^,\.]+)"),
            "ram": pick(r"RAM\s*:\s*([^,\.]+)"),
            "ssd": pick(r"SSD\s*:\s*([^,\.]+)"),
            "screen": pick(r"Screen\s*:\s*([^,\.]+)"),
            "battery": pick(r"Battery\s*:\s*([^,\.]+)"),
            "brand": pick(r"Brand\s*:\s*([^,\.]+)"),
        }
        return {k: v for k, v in specs.items() if v}

    def _spec_value_explanation(self, key, value):
        """Diễn giải ý nghĩa thông số bằng ngôn ngữ tư vấn, tránh liệt kê khô."""
        k = key.lower()
        if k == "ram":
            return f"RAM {value} giúp bạn đa nhiệm mượt hơn, mở nhiều ứng dụng/tab cùng lúc ít giật lag."
        if k == "ssd":
            return f"SSD {value} cho tốc độ mở máy và mở ứng dụng nhanh, phản hồi hệ thống tốt hơn HDD truyền thống."
        if k == "cpu":
            return f"CPU {value} là nền tảng chính cho hiệu năng tổng thể, ảnh hưởng trực tiếp tới tốc độ xử lý công việc."
        if k == "gpu":
            return f"GPU {value} hỗ trợ mạnh cho gaming/đồ họa, giúp xử lý hình ảnh và render tốt hơn."
        if k == "screen":
            return f"Màn hình {value} ảnh hưởng trực tiếp tới trải nghiệm nhìn, làm việc và giải trí mỗi ngày."
        if k == "battery":
            return f"Pin {value} phù hợp khi bạn cần di chuyển nhiều và làm việc liên tục."
        return f"{key.upper()}: {value}."

    def _summarize_product_for_advice(self, doc, meta):
        """Tạo đoạn mô tả tư vấn ngắn gọn cho 1 sản phẩm."""
        category = (meta or {}).get("category", "N/A")
        price = (meta or {}).get("price", "N/A")

        name_match = re.search(r"Sản phẩm\s*:\s*([^\.]+)", doc or "", flags=re.IGNORECASE)
        if name_match:
            name = name_match.group(1).strip()
        else:
            # fallback cho dữ liệu cũ dạng "Laptop Dell XPS 15..."
            first_sentence = (doc or "").split(".")[0].strip()
            name = first_sentence if first_sentence else "Sản phẩm phù hợp"

        specs = self._extract_specs(doc)
        rationale = []
        for key in ["cpu", "gpu", "ram", "ssd", "screen", "battery"]:
            if key in specs:
                rationale.append(self._spec_value_explanation(key, specs[key]))

        if not rationale:
            rationale.append("Mẫu này có mô tả phù hợp với nhu cầu bạn đang hỏi trong dữ liệu hiện tại của TechShop.")

        return {
            "name": name,
            "category": category,
            "price": price,
            "rationale": rationale[:3],
            "specs": specs,
        }

    def _rerank_by_laptop_performance(self, search_results):
        docs = search_results["documents"][0]
        metas = search_results["metadatas"][0]
        dists = search_results["distances"][0]
        if not docs:
            return search_results

        scored = []
        for doc, meta, dist in zip(docs, metas, dists):
            perf = self._score_laptop_performance(doc, meta)
            scored.append((perf, float(dist), doc, meta, dist))

        scored.sort(key=lambda x: (-x[0], x[1]))
        return {
            "documents": [[x[2] for x in scored]],
            "metadatas": [[x[3] for x in scored]],
            "distances": [[x[4] for x in scored]],
        }

    def _extract_category_intent(self, query):
        """Nhận diện người dùng có đang hỏi rõ một loại sản phẩm không."""
        q = self._strip_accents((query or "").lower())
        mapping = {
            "laptop": "laptop",
            "notebook": "laptop",
            "dien thoai": "mobile",
            "smartphone": "mobile",
            "phone": "mobile",
            "mobile": "mobile",
            "tablet": "tablet",
            "may tinh bang": "tablet",
            "phu kien": "accessory",
            "accessory": "accessory",
            "smartwatch": "smartwatch",
            "dong ho thong minh": "smartwatch",
            "watch": "smartwatch",
        }
        intents = set()
        for key, cat in mapping.items():
            if key in q:
                intents.add(self._normalize_category(cat))
        return intents

    @staticmethod
    def _is_generic_summary_query(query):
        q = (query or "").lower()
        patterns = [
            "tóm tắt", "tom tat", "tốt nhất", "tot nhat", "nhiều lựa chọn", "nhieu lua chon",
            "gợi ý", "goi y", "sản phẩm tốt", "san pham tot"
        ]
        return any(p in q for p in patterns)

    def _apply_category_scope(self, query, search_results):
        """Mặc định giới hạn vào danh mục chính; nếu user nêu loại rõ ràng thì ưu tiên theo loại đó."""
        docs = search_results["documents"][0]
        metas = search_results["metadatas"][0]
        dists = search_results["distances"][0]
        if not docs:
            return search_results

        intents = self._extract_category_intent(query)
        if intents:
            allowed = intents
        else:
            allowed = self.primary_categories

        filtered_docs, filtered_meta, filtered_dist = [], [], []
        for doc, meta, dist in zip(docs, metas, dists):
            category = self._normalize_category((meta or {}).get("category"))
            if category not in allowed:
                continue
            filtered_docs.append(doc)
            filtered_meta.append(meta)
            filtered_dist.append(dist)

        return {
            "documents": [filtered_docs],
            "metadatas": [filtered_meta],
            "distances": [filtered_dist],
        }

    @staticmethod
    def _diversify_by_category(search_results, k):
        """Round-robin theo category để top-k không dồn một loại."""
        docs = search_results["documents"][0]
        metas = search_results["metadatas"][0]
        dists = search_results["distances"][0]
        if not docs:
            return search_results

        buckets = {}
        for doc, meta, dist in zip(docs, metas, dists):
            cat = ((meta or {}).get("category") or "N/A")
            buckets.setdefault(cat, []).append((doc, meta, dist))

        ordered_cats = sorted(buckets.keys(), key=lambda c: len(buckets[c]), reverse=True)
        merged = []
        while len(merged) < k:
            progressed = False
            for cat in ordered_cats:
                if buckets[cat]:
                    merged.append(buckets[cat].pop(0))
                    progressed = True
                    if len(merged) >= k:
                        break
            if not progressed:
                break

        return {
            "documents": [[x[0] for x in merged]],
            "metadatas": [[x[1] for x in merged]],
            "distances": [[x[2] for x in merged]],
        }

    def _rerank_by_keywords(self, search_results, user_query, require_overlap=True):
        """Ưu tiên các sản phẩm có chứa từ khóa người dùng (không dấu)."""
        docs = search_results["documents"][0]
        metas = search_results["metadatas"][0]
        dists = search_results["distances"][0]

        if not docs:
            return search_results

        query_tokens = self._tokenize_query(user_query)
        if not query_tokens:
            return search_results

        ranked = []
        for doc, meta, dist in zip(docs, metas, dists):
            searchable = self._strip_accents(
                f"{doc} {(meta or {}).get('category', '')} {(meta or {}).get('price', '')}".lower()
            )
            searchable_tokens = set(re.findall(r"\w+", searchable))
            overlap = sum(1 for token in query_tokens if token in searchable_tokens)
            ranked.append((overlap, float(dist), doc, meta, dist))

        max_overlap = max(item[0] for item in ranked)
        if require_overlap and max_overlap > 0:
            ranked = [item for item in ranked if item[0] > 0]

        ranked.sort(key=lambda x: (-x[0], x[1]))

        return {
            "documents": [[item[2] for item in ranked]],
            "metadatas": [[item[3] for item in ranked]],
            "distances": [[item[4] for item in ranked]],
        }

    @staticmethod
    def _take_top_k(search_results, k):
        return {
            "documents": [search_results["documents"][0][:k]],
            "metadatas": [search_results["metadatas"][0][:k]],
            "distances": [search_results["distances"][0][:k]],
        }

    def _fetch_live_products(self, query):
        """
        Lấy dữ liệu mới nhất từ API live (gateway -> customer search).
        Đây là nguồn dữ liệu authoritative để chốt tên/giá, tránh hallucination giá cũ từ vector DB.
        """
        def _request(q):
            params = urlencode({"q": q or ""})
            url = f"{self.live_search_url}?{params}"
            try:
                req = Request(url, headers={"Accept": "application/json"})
                with urlopen(req, timeout=5) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                return payload if isinstance(payload, dict) else {}
            except (URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
                logger.warning(f"Cannot fetch live catalog from {url}: {exc}")
                return {}

        def _flatten(raw_dict):
            products_local = []
            seen_local = set()
            for product_type, items in raw_dict.items():
                if not isinstance(items, list):
                    continue

                normalized_type = self._normalize_category(product_type)
                for item in items:
                    if not isinstance(item, dict):
                        continue

                    pid = item.get("id")
                    if pid is None:
                        continue

                    price_vnd = self._parse_price_to_vnd(item.get("price"))
                    if price_vnd is None:
                        continue

                    key = (normalized_type, str(pid))
                    if key in seen_local:
                        continue
                    seen_local.add(key)

                    products_local.append({
                        "id": str(pid),
                        "category": normalized_type,
                        "name": str(item.get("name", "")).strip(),
                        "brand": str(item.get("brand", "")).strip(),
                        "price": price_vnd,
                        "description": str(item.get("description", "")).strip(),
                        "quantity": item.get("quantity", 0),
                    })
            return products_local

        raw = _request(query)
        products = _flatten(raw)

        # Fallback full catalog cho truy vấn mua hàng (kể cả khi không nêu rõ category).
        # Chỉ chặn fallback với small-talk để tránh trả lời lệch ngữ cảnh.
        if not products and not self._is_smalltalk_query(query):
            products = _flatten(_request(""))

        return products

    def _build_vector_rank_maps(self, search_results):
        """Trả về ranking map theo (category,id) để kết hợp vector retrieval với dữ liệu live."""
        docs = search_results["documents"][0]
        metas = search_results["metadatas"][0]
        dists = search_results["distances"][0]

        rank_map = {}
        perf_map = {}

        for idx, (doc, meta, dist) in enumerate(zip(docs, metas, dists)):
            item_id = (meta or {}).get("id") or (meta or {}).get("product_id")
            category = self._normalize_category((meta or {}).get("category"))
            if item_id is None or not category:
                continue

            key = (category, str(item_id))
            rank_map[key] = {
                "rank": idx,
                "similarity": self._normalize_similarity(dist),
            }
            perf_map[key] = self._score_laptop_performance(doc, meta)

        return rank_map, perf_map

    @staticmethod
    def _format_vnd(price_vnd):
        try:
            value = int(round(float(price_vnd)))
        except (TypeError, ValueError):
            return "N/A"
        return f"{value:,}".replace(",", ".") + "đ"

    def _build_structured_context(self, products):
        """Format context rõ ràng để hạn chế nhầm lẫn giữa các sản phẩm."""
        lines = ["[Context]"]
        for p in products:
            lines.append(json.dumps({
                "product_id": p["id"],
                "category": p["category"],
                "name": p["name"],
                "brand": p["brand"],
                "price_vnd": int(p["price"]),
                "quantity": p.get("quantity", 0),
                "description": p.get("description", ""),
                "similarity": round(float(p.get("similarity", 0.0)), 4),
            }, ensure_ascii=False))
        return "\n".join(lines)

    def _build_budget_no_match_reply(self, user_query):
        """Trả lời mềm khi không có mẫu đúng dải giá, nhưng vẫn tôn trọng ràng buộc ngân sách."""
        constraints = self._extract_price_constraints(user_query)
        min_price = constraints.get("min_price")
        max_price = constraints.get("max_price")

        if min_price is None and max_price is None:
            return None

        live_products = self._fetch_live_products(user_query)
        if not live_products:
            return None

        intents = self._extract_category_intent(user_query)
        if intents:
            live_products = [p for p in live_products if p.get("category") in intents]
        else:
            live_products = [p for p in live_products if p.get("category") in self.primary_categories]

        if not live_products:
            return None

        if min_price is not None and max_price is not None:
            below_min = [p for p in live_products if p.get("price") is not None and p["price"] < float(min_price)]
            at_or_below_max = [p for p in live_products if p.get("price") is not None and p["price"] <= float(max_price)]

            if at_or_below_max:
                best_under_cap = max(at_or_below_max, key=lambda x: x["price"])
                return (
                    f"Hiện TechShop chưa có mẫu đúng trong khoảng {self._format_vnd(min_price)} đến {self._format_vnd(max_price)}. "
                    f"Nếu bạn giữ trần ngân sách {self._format_vnd(max_price)}, mẫu gần nhất là "
                    f"{best_under_cap.get('name')} ({best_under_cap.get('category')}) giá {self._format_vnd(best_under_cap.get('price'))}."
                )

            if below_min:
                best_below = max(below_min, key=lambda x: x["price"])
                return (
                    f"Hiện TechShop chưa có mẫu trong khoảng {self._format_vnd(min_price)} đến {self._format_vnd(max_price)}. "
                    f"Phương án gần nhất dưới ngưỡng này là {best_below.get('name')} "
                    f"({best_below.get('category')}) giá {self._format_vnd(best_below.get('price'))}."
                )

        if max_price is not None:
            at_or_below_max = [p for p in live_products if p.get("price") is not None and p["price"] <= float(max_price)]
            if at_or_below_max:
                best_under_cap = max(at_or_below_max, key=lambda x: x["price"])
                return (
                    f"Hiện chưa có mẫu khớp hoàn toàn mô tả, nhưng nếu giữ trần {self._format_vnd(max_price)} "
                    f"thì lựa chọn gần nhất là {best_under_cap.get('name')} "
                    f"({best_under_cap.get('category')}) giá {self._format_vnd(best_under_cap.get('price'))}."
                )

        return None

    def _select_grounded_products(self, user_query, search_results, limit=3):
        """
        Kết hợp Vector Retrieval + dữ liệu live để chọn sản phẩm chính xác thực tế.
        Đây là bước thay cho việc chỉ tin vào vector metadata cũ.
        """
        live_products = self._fetch_live_products(user_query)
        if not live_products:
            return []

        intents = self._extract_category_intent(user_query)
        if intents:
            live_products = [p for p in live_products if p["category"] in intents]
        else:
            # Query mơ hồ: chỉ giữ danh mục chính để không trả lời lạc sang nhóm phụ.
            live_products = [p for p in live_products if p["category"] in self.primary_categories]
        if not live_products:
            return []

        # Áp ràng buộc giá cứng ngay trên dữ liệu live để không vượt ngân sách người dùng.
        price_constraints = self._extract_price_constraints(user_query)
        min_price = price_constraints.get("min_price")
        max_price = price_constraints.get("max_price")
        if min_price is not None:
            live_products = [p for p in live_products if p["price"] >= float(min_price)]
        if max_price is not None:
            live_products = [p for p in live_products if p["price"] <= float(max_price)]
        if not live_products:
            return []

        query_norm = self._strip_accents((user_query or "").lower())
        is_price_lookup = any(k in query_norm for k in ["gia", "bao nhieu", "price"])
        query_tokens = set(self._tokenize_query(user_query))

        rank_map, perf_map = self._build_vector_rank_maps(search_results)

        # Truy vấn hỏi giá theo tên model: ưu tiên match tên thực trong dữ liệu live.
        if query_tokens:
            for p in live_products:
                name_tokens = set(re.findall(r"\w+", self._strip_accents(p["name"].lower())))
                p["name_overlap"] = sum(1 for t in query_tokens if t in name_tokens)

            max_overlap = max((p.get("name_overlap", 0) for p in live_products), default=0)
            if is_price_lookup and max_overlap >= 2:
                name_matched = [p for p in live_products if p.get("name_overlap", 0) == max_overlap]
                name_matched.sort(key=lambda x: x["price"])
                return name_matched[:1]

        intent = self._detect_intent(user_query)

        # Query kiểu "rẻ nhất" cần chính xác giá thực tế -> không ép nằm trong vector top-k.
        if intent == "budget":
            live_products.sort(key=lambda x: x["price"])
            return live_products[: min(limit, 2)]

        # Với các intent khác, ưu tiên intersection với vector candidates nếu có.
        vector_keys = set(rank_map.keys())
        if vector_keys:
            candidates = [p for p in live_products if (p["category"], p["id"]) in vector_keys]
            if candidates:
                live_products = candidates

        for p in live_products:
            key = (p["category"], p["id"])
            p["similarity"] = rank_map.get(key, {}).get("similarity", 0.0)
            p["perf_score"] = perf_map.get(key, 0.0)

        # Query kiểu "mạnh nhất": ưu tiên perf score, tie-break bằng similarity.
        if intent == "best_performance":
            live_products.sort(
                key=lambda x: (
                    -x.get("perf_score", 0.0),
                    -x.get("similarity", 0.0),
                    x["price"],
                )
            )
            return live_products[: min(limit, 2)]

        # Query thường: ưu tiên similarity (vector), tie-break giá thấp hơn.
        live_products.sort(key=lambda x: (-x.get("similarity", 0.0), x["price"]))
        return live_products[:limit]

    @staticmethod
    def _empty_results():
        return {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

    @staticmethod
    def _extract_price_constraints(query):
        """Phân tích ràng buộc giá từ câu hỏi tiếng Việt (đơn vị VND)."""
        q = AIConsultant._strip_accents((query or "").lower())
        constraints = {"min_price": None, "max_price": None}

        amount_matches = list(re.finditer(r"(\d+(?:[\.,]\d+)?)\s*(trieu|tr|m|nghin|k)?", q))

        def to_vnd(match):
            number = float(match.group(1).replace(",", "."))
            unit = (match.group(2) or "").strip()
            if unit in {"trieu", "tr", "m"}:
                return number * 1_000_000
            if unit in {"nghin", "k"}:
                return number * 1_000
            # Mặc định coi là VND trực tiếp
            return number

        # Khoảng giá: "20-30 trieu", "tu 20 den 30 trieu"
        range_m = re.search(
            r"(?:tu\s+)?(\d+(?:[\.,]\d+)?)\s*(trieu|tr|m|nghin|k)?\s*(?:-|den|toi)\s*(\d+(?:[\.,]\d+)?)\s*(trieu|tr|m|nghin|k)?",
            q
        )
        if range_m:
            low = float(range_m.group(1).replace(",", "."))
            low_unit = range_m.group(2) or range_m.group(4) or ""
            high = float(range_m.group(3).replace(",", "."))
            high_unit = range_m.group(4) or range_m.group(2) or ""
            # Dùng logic giống to_vnd nhưng không lặp code nhiều
            low_vnd = low * (1_000_000 if low_unit in {"trieu", "tr", "m"} else 1_000 if low_unit in {"nghin", "k"} else 1)
            high_vnd = high * (1_000_000 if high_unit in {"trieu", "tr", "m"} else 1_000 if high_unit in {"nghin", "k"} else 1)
            constraints["min_price"] = min(low_vnd, high_vnd)
            constraints["max_price"] = max(low_vnd, high_vnd)
            return constraints

        # Chỉ có một mức giá: xét từ khóa so sánh
        if amount_matches:
            amount_vnd = to_vnd(amount_matches[0])
            if re.search(r"(>=|>)|\b(tren|hon|lon\s+hon)\b", q):
                constraints["min_price"] = amount_vnd
            elif re.search(r"(<=|<)|\b(duoi|nho\s+hon|khong\s+hon|toi\s+da)\b", q):
                constraints["max_price"] = amount_vnd
            elif re.search(r"\b(tam|khoang|quanh)\b", q):
                # "tầm 20 triệu" => khoảng mềm +/-20%
                constraints["min_price"] = amount_vnd * 0.8
                constraints["max_price"] = amount_vnd * 1.2
            elif re.search(r"(muon|tim|mua|goi y|tu van)", q):
                # Có 1 mốc giá trong câu hỏi mua hàng: mặc định coi là trần ngân sách.
                constraints["max_price"] = amount_vnd

        return constraints

    def _apply_constraints(self, query, search_results):
        """Lọc kết quả retrieval theo các ràng buộc ngữ nghĩa (hiện tại: giá)."""
        constraints = self._extract_price_constraints(query)
        min_price = constraints["min_price"]
        max_price = constraints["max_price"]

        if min_price is None and max_price is None:
            return search_results

        filtered_docs, filtered_meta, filtered_dist = [], [], []
        for doc, meta, dist in zip(
            search_results["documents"][0],
            search_results["metadatas"][0],
            search_results["distances"][0],
        ):
            price_vnd = self._parse_price_to_vnd((meta or {}).get("price"))
            if price_vnd is None:
                continue
            if min_price is not None and price_vnd < min_price:
                continue
            if max_price is not None and price_vnd > max_price:
                continue
            filtered_docs.append(doc)
            filtered_meta.append(meta)
            filtered_dist.append(dist)

        return {
            "documents": [filtered_docs],
            "metadatas": [filtered_meta],
            "distances": [filtered_dist],
        }

    def add_product_to_knowledge_base(self, product_id, content, metadata=None):
        """
        Thêm/cập nhật sản phẩm vào Vector Database (ChromaDB).
        Được gọi từ Django Signal (qua FastAPI endpoint /api/vectorize).

        Args:
            product_id: ID sản phẩm
            content: Nội dung text mô tả sản phẩm (đã format)
            metadata: Dict metadata phụ trợ {category, price, id}
        """
        if metadata is None:
            metadata = {}

        try:
            # Upsert: thêm mới hoặc cập nhật nếu đã tồn tại
            self.collection.upsert(
                ids=[str(product_id)],
                documents=[content],
                metadatas=[metadata]
            )
            logger.info(f"✅ Product {product_id} đã được vectorize vào ChromaDB.")
            return True
        except Exception as e:
            logger.error(f"❌ Lỗi vectorize product {product_id}: {e}")
            return False

    def get_advice(self, user_query, k=3):
        """
        Hàm chính: Tìm kiếm sản phẩm liên quan (Similarity Search)
        rồi tạo câu trả lời tư vấn cho khách hàng.

        Flow RAG:
        1. Embed user_query → vector
        2. Similarity Search trong ChromaDB → top-k documents
        3. Ghép context + template → trả lời tư vấn

        Args:
            user_query: Câu hỏi của khách hàng
            k: Số lượng sản phẩm tương tự cần lấy

        Returns:
            str: Câu trả lời tư vấn
        """
        if self._is_smalltalk_query(user_query):
            return (
                "Mình luôn sẵn sàng hỗ trợ bạn chọn sản phẩm. "
                "Bạn có thể nói rõ nhu cầu như loại máy, ngân sách, hoặc mẫu bạn đang quan tâm nhé."
            )

        # Kiểm tra có dữ liệu không
        if self.collection.count() == 0:
            return ("Xin lỗi, hệ thống chưa có dữ liệu sản phẩm. "
                    "Vui lòng thêm sản phẩm vào hệ thống trước.")

        try:
            target_k = self._determine_target_k(user_query, default_k=k)

            # B1: Retrieval lấy rộng 5-10 ứng viên để có ngữ cảnh tốt hơn.
            # Nếu DB có ít hơn 5 item, lấy toàn bộ số hiện có.
            total_docs = self.collection.count()
            if total_docs >= self.retrieval_min_k:
                n_candidates = min(total_docs, self.retrieval_max_k)
            else:
                n_candidates = total_docs

            results = self.collection.query(
                query_texts=[user_query],
                n_results=n_candidates,
                include=["documents", "metadatas", "distances"]
            )

            # B1.0: Giới hạn phạm vi theo danh mục phù hợp với web/catalog
            results = self._apply_category_scope(user_query, results)

            # B1.1: Lọc theo điều kiện (giá,...) rút ra từ câu hỏi.
            # Không fallback về kết quả cũ để tránh trả lời lệch nhu cầu thực tế.
            results = self._apply_constraints(user_query, results)

            if not results["documents"][0]:
                results = self._empty_results()

            is_generic = self._is_generic_summary_query(user_query)

            # B1.2: Rerank bằng từ khóa để bám sát intent người dùng.
            results = self._rerank_by_keywords(results, user_query, require_overlap=not is_generic)

            if not results["documents"][0]:
                results = self._empty_results()

            # B1.2b: Nếu user hỏi cấu hình laptop mạnh nhất -> rerank theo điểm hiệu năng.
            if self._is_laptop_performance_query(user_query):
                results = self._rerank_by_laptop_performance(results)

            # B1.3: Ngưỡng an toàn similarity để loại kết quả nhiễu.
            # Nếu không có item nào đạt ngưỡng => context rỗng, không trả lời đoán mò.
            results = self._filter_by_similarity_threshold(results, query=user_query)

            if not results or not results['documents'] or not results['documents'][0]:
                logger.info("No safe vector match above threshold. Fallback to live grounding only.")
                results = self._empty_results()

            # B1.4: Với câu hỏi tổng quát, cân bằng danh mục trong top-k hiển thị.
            if is_generic:
                results = self._diversify_by_category(results, target_k)
            else:
                results = self._take_top_k(results, target_k)

            # B2: Grounding với dữ liệu live để tránh giá/tên bị cũ hoặc hallucination.
            grounded_products = self._select_grounded_products(user_query, results, limit=target_k)
            if not grounded_products:
                budget_no_match = self._build_budget_no_match_reply(user_query)
                if budget_no_match:
                    return budget_no_match
                return "Rất tiếc, TechShop hiện chưa có sản phẩm này"

            # B3: Context có cấu trúc rõ ràng.
            context_text = self._build_structured_context(grounded_products)

            # B4: Tạo câu trả lời tư vấn (chỉ dựa dữ liệu grounded)
            response = self._generate_advice(user_query, context_text, grounded_products)

            return response

        except Exception as e:
            logger.error(f"❌ Lỗi get_advice: {e}")
            return f"Xin lỗi, đã có lỗi xảy ra khi xử lý câu hỏi của bạn: {str(e)}"

    def _generate_advice(self, query, context_text, grounded_products):
        """
        Tạo câu trả lời tư vấn dựa trên context.
        Chạy hoàn toàn local (rule-based), không cần API key.
        
        Nếu muốn nâng cấp lên LLM, chỉ cần thay hàm này bằng:
        - OpenAI GPT (cần API key)
        - Ollama local LLM (cần cài Ollama)
        """
        if not context_text.strip() or not grounded_products:
            return "Rất tiếc, TechShop hiện chưa có sản phẩm này"

        intent = self._detect_intent(query)

        greeting = f"Mình đã xem dữ liệu sản phẩm hiện có của TechShop theo nhu cầu '{query}'."

        if intent == "best_performance":
            focus = grounded_products[:2]
            top1 = focus[0]
            answer = (
                f"{greeting} Nếu ưu tiên cấu hình mạnh nhất, mình nghiêng về {top1['name']} "
                f"({top1['category']}, {self._format_vnd(top1['price'])}) vì mô tả hiện tại cho thấy mức hiệu năng nổi bật trong nhóm phù hợp."
            )

            if len(focus) > 1:
                top2 = focus[1]
                answer += (
                    f" Phương án thay thế đáng cân nhắc là {top2['name']} "
                    f"({self._format_vnd(top2['price'])}), phù hợp nếu bạn muốn cân bằng thêm giữa hiệu năng và chi phí."
                )

            return answer + " Nếu bạn muốn, mình có thể chốt nhanh 1 lựa chọn theo ngân sách cụ thể."

        # Intent còn lại: trả lời tự nhiên, chỉ nêu các lựa chọn liên quan.
        options = grounded_products[:3]
        snippets = []
        for p in options:
            snippets.append(
                f"{p['name']} ({p['category']}, {self._format_vnd(p['price'])})"
            )

        if len(snippets) == 1:
            core = snippets[0]
        elif len(snippets) == 2:
            core = f"{snippets[0]}. Ngoài ra, {snippets[1]}."
        else:
            core = f"{snippets[0]}. Bạn cũng có thể cân nhắc {snippets[1]}. Thêm một lựa chọn gần nhu cầu là {snippets[2]}."

        return (
            f"{greeting} {core} "
            "Bạn chia sẻ thêm ngân sách và ưu tiên chính (hiệu năng, pin, màn hình hay độ nhẹ), mình sẽ lọc hẹp còn 1-2 mẫu sát nhất."
        )

    @staticmethod
    def _name_tokens(text):
        return set(re.findall(r"\w+", AIConsultant._strip_accents((text or "").lower())))

    def _score_product_against_constraints(self, product, constraints, query_tokens):
        checks = 0
        matched = 0

        p_category = self._normalize_category(product.get("category"))
        p_brand = self._strip_accents((product.get("brand") or "").lower())
        p_name_tokens = self._name_tokens(product.get("name"))
        p_price = self._parse_price_to_vnd(product.get("price"))

        category = constraints.get("category")
        if category:
            checks += 1
            if p_category == self._normalize_category(category):
                matched += 1

        brands = constraints.get("brands") or []
        if brands:
            checks += 1
            if any(self._strip_accents(b.lower()) in p_brand or self._strip_accents(b.lower()) in " ".join(p_name_tokens) for b in brands):
                matched += 1

        min_price = constraints.get("min_price")
        if min_price is not None:
            checks += 1
            if p_price is not None and p_price >= float(min_price):
                matched += 1

        max_price = constraints.get("max_price")
        if max_price is not None:
            checks += 1
            if p_price is not None and p_price <= float(max_price):
                matched += 1

        # Match tên sản phẩm user nêu trực tiếp
        specific_models = constraints.get("specific_models") or []
        if specific_models:
            checks += 1
            if any(self._strip_accents(name.lower()) in self._strip_accents((product.get("name") or "").lower()) for name in specific_models):
                matched += 1

        # Tăng điểm nhẹ nếu tên sản phẩm có overlap token với query
        overlap = len(query_tokens.intersection(p_name_tokens))
        overlap_bonus = min(overlap * 0.05, 0.2)

        if checks == 0:
            return min(0.6 + overlap_bonus, 1.0)

        return min((matched / checks) + overlap_bonus, 1.0)

    def _build_context_from_products(self, products):
        lines = ["[Context]"]
        for p in products:
            lines.append(json.dumps({
                "product_id": p.get("id"),
                "name": p.get("name"),
                "category": p.get("category"),
                "brand": p.get("brand", ""),
                "price_vnd": int(round(float(p.get("price", 0)))),
                "stock": p.get("stock", 0),
                "description": p.get("description", ""),
                "attributes": p.get("attributes", {}),
                "score": round(float(p.get("score", 0.0)), 4),
            }, ensure_ascii=False))
        return "\n".join(lines)

    def get_grounded_advice(self, query, context_products, constraints=None):
        """
        Sinh câu trả lời strict-grounded từ context ORM đã lọc cứng từ Django.
        Rule: không vượt ngân sách, không bịa dữ liệu, và chỉ dựa [Context].
        """
        constraints = constraints or {}
        context_products = context_products or []

        fallback_msg = "Rất tiếc, TechShop hiện không có sản phẩm nào thỏa mãn đúng yêu cầu của bạn"

        if not context_products:
            return fallback_msg

        query_norm = self._strip_accents((query or "").lower())
        query_tokens = set(self._tokenize_query(query))

        # Hard rule: không cho phép vượt ngân sách max_price dù chỉ 1 đồng.
        max_price = constraints.get("max_price")
        if max_price is not None:
            context_products = [
                p for p in context_products
                if self._parse_price_to_vnd(p.get("price")) is not None and self._parse_price_to_vnd(p.get("price")) <= float(max_price)
            ]

        if not context_products:
            return fallback_msg

        # Nếu khách yêu cầu so sánh 2 sản phẩm cụ thể, chỉ giữ đúng các sản phẩm đó.
        specific_models = constraints.get("specific_models") or []
        if specific_models:
            filtered = [
                p for p in context_products
                if any(self._strip_accents(name.lower()) in self._strip_accents((p.get("name") or "").lower()) for name in specific_models)
            ]
            if filtered:
                context_products = filtered
            else:
                missing = ", ".join(specific_models)
                return f"Hiện TechShop chưa có sản phẩm {missing}. {fallback_msg}"

        # Chấm điểm mức độ phù hợp theo constraints; chỉ giữ >70%.
        scored = []
        for p in context_products:
            score = self._score_product_against_constraints(p, constraints, query_tokens)
            p2 = dict(p)
            p2["score"] = score
            scored.append(p2)

        eligible = [p for p in scored if p.get("score", 0.0) >= 0.7]
        if not eligible:
            return fallback_msg

        intent = self._detect_intent(query)

        # "rẻ nhất": chọn đúng giá thấp nhất trong eligible.
        if intent == "budget" or "re nhat" in query_norm:
            best = min(eligible, key=lambda x: self._parse_price_to_vnd(x.get("price")) or float("inf"))
            context_text = self._build_context_from_products([best])
            return (
                f"Mình đã đối chiếu đúng dữ liệu TechShop trong [Context]. Mẫu rẻ nhất phù hợp hiện tại là "
                f"{best.get('name')} ({best.get('category')}) với giá {self._format_vnd(best.get('price'))}."
            )

        # "mạnh nhất": ưu tiên điểm hiệu năng cho laptop, còn lại dùng score.
        if intent == "best_performance" or "manh nhat" in query_norm:
            laptop_like = [p for p in eligible if self._normalize_category(p.get("category")) == "laptop"]
            if laptop_like:
                ranked = sorted(
                    laptop_like,
                    key=lambda p: -self._score_laptop_performance(
                        f"Sản phẩm: {p.get('name')}. Mô tả: {p.get('description')}.",
                        {"price": str(p.get("price")), "category": p.get("category")}
                    )
                )
            else:
                ranked = sorted(eligible, key=lambda x: -x.get("score", 0.0))

            focus = ranked[:2]
            if len(focus) == 1:
                p = focus[0]
                return (
                    f"Trong dữ liệu hiện có của TechShop, lựa chọn mạnh nhất phù hợp là {p.get('name')} "
                    f"với giá {self._format_vnd(p.get('price'))}."
                )
            p1, p2 = focus[0], focus[1]
            return (
                f"Nếu ưu tiên mạnh nhất, mình chọn {p1.get('name')} ({self._format_vnd(p1.get('price'))}). "
                f"Phương án thay thế gần nhất là {p2.get('name')} ({self._format_vnd(p2.get('price'))})."
            )

        # Query giá theo model cụ thể
        if any(k in query_norm for k in ["gia", "bao nhieu"]):
            ranked = sorted(eligible, key=lambda x: (-x.get("score", 0.0), self._parse_price_to_vnd(x.get("price")) or float("inf")))
            top = ranked[0]
            return f"Theo dữ liệu hiện tại của TechShop, {top.get('name')} có giá {self._format_vnd(top.get('price'))}."

        # Mặc định: top 2 ngắn gọn, tập trung lý do đúng yêu cầu.
        ranked = sorted(eligible, key=lambda x: (-x.get("score", 0.0), self._parse_price_to_vnd(x.get("price")) or float("inf")))
        top = ranked[:2]
        if len(top) == 1:
            p = top[0]
            return (
                f"Mình gợi ý {p.get('name')} ({p.get('category')}) với giá {self._format_vnd(p.get('price'))}, "
                "vì đây là lựa chọn sát yêu cầu nhất trong dữ liệu hiện có."
            )
        p1, p2 = top[0], top[1]
        return (
            f"Mình đề xuất {p1.get('name')} ({self._format_vnd(p1.get('price'))}) vì phù hợp yêu cầu hơn. "
            f"Bạn có thể so sánh thêm với {p2.get('name')} ({self._format_vnd(p2.get('price'))}) để cân bằng thêm ngân sách/tính năng."
        )

    def get_collection_stats(self):
        """Trả về thống kê của Vector Database."""
        return {
            "total_documents": self.collection.count(),
            "collection_name": self.collection.name,
        }

    @staticmethod
    def get_reindex_cron_recommendation():
        """
        Gợi ý CRON để đồng bộ dữ liệu Product -> Vector DB định kỳ.
        Chạy script sync_ai.py ở service Django (nơi có ORM Product).
        """
        return "*/30 * * * * cd /path/to/techshop/web && python /path/to/sync_ai.py"


if __name__ == "__main__":
    # Test mẫu độc lập
    consultant = AIConsultant()

    # Thêm sản phẩm mẫu
    consultant.add_product_to_knowledge_base(
        product_id=1,
        content="Laptop Dell XPS 15. RAM 16GB, SSD 512GB, CPU Intel i7. Giá 35,000,000 VNĐ. "
                "Phù hợp cho lập trình và đồ hoạ.",
        metadata={"category": "Laptop", "price": "35000000", "id": 1}
    )
    consultant.add_product_to_knowledge_base(
        product_id=2,
        content="MacBook Pro 14 M3. RAM 18GB, SSD 512GB, Chip Apple M3 Pro. Giá 52,000,000 VNĐ. "
                "Laptop cao cấp cho developer.",
        metadata={"category": "Laptop", "price": "52000000", "id": 2}
    )

    # Test tư vấn
    print(consultant.get_advice("Tôi muốn mua laptop lập trình, tầm 30-40 triệu"))
