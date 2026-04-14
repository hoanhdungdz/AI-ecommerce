"""
TechShop AI Service — FastAPI Application
Xử lý các tác vụ Deep Learning (Behavior Analysis) và RAG (Chatbot Consultant).

Endpoints:
- POST /api/vectorize  — Nhận webhook từ Django khi Product thay đổi, lưu vào ChromaDB
- GET  /api/chat       — RAG Chatbot tư vấn sản phẩm
- POST /api/predict    — Deep Learning dự đoán sản phẩm tiếp theo
- GET  /api/stats      — Thống kê Vector Database
- GET  /health         — Health check
"""
import logging
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="TechShop AI Service",
    description="Behavior Analysis (Deep Learning) + RAG Consultant (Chatbot) API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# Lazy Initialization (tránh crash khi khởi động)
# ============================================================
_consultant = None
_dl_model = None


def get_consultant():
    """Lazy load AIConsultant (RAG Chatbot)."""
    global _consultant
    if _consultant is None:
        try:
            from rag.consultant import AIConsultant
            _consultant = AIConsultant()
            logger.info("✅ AIConsultant initialized.")
        except Exception as e:
            logger.error(f"❌ Failed to init AIConsultant: {e}")
            raise HTTPException(status_code=500, detail=f"AIConsultant init error: {str(e)}")
    return _consultant


def get_dl_model():
    """Lazy load Deep Learning model."""
    global _dl_model
    if _dl_model is None:
        try:
            from dl_model.behavior_model import load_or_build_model
            _dl_model = load_or_build_model()
            logger.info("✅ DL Model initialized.")
        except Exception as e:
            logger.warning(f"⚠️ DL Model init failed (non-critical): {e}")
    return _dl_model


# ============================================================
# Pydantic Models
# ============================================================
class ProductData(BaseModel):
    """Dữ liệu sản phẩm từ Django Signal."""
    product_id: str
    category: str
    name: str
    price: str
    description: Optional[str] = ""
    attributes: Optional[Dict[str, Any]] = {}


class PredictRequest(BaseModel):
    """Request cho behavior prediction."""
    product_ids: List[int]
    top_k: Optional[int] = 5


class GroundedChatRequest(BaseModel):
    """Request cho grounded chatbot: context đã được hard-filter từ Django ORM."""
    query: str
    context_products: List[Dict[str, Any]] = []
    constraints: Optional[Dict[str, Any]] = {}


# ============================================================
# API Endpoints
# ============================================================

@app.post("/api/vectorize")
async def vectorize_product(data: ProductData, background_tasks: BackgroundTasks):
    """
    Nhận webhook từ Django Signal khi Product được tạo/cập nhật.
    Vectorize nội dung sản phẩm và lưu vào ChromaDB (Background Task).
    """
    # Tạo nội dung text để vectorize
    content = (
        f"Sản phẩm: {data.name}. "
        f"Thuộc danh mục: {data.category}. "
        f"Giá: {data.price} VNĐ. "
        f"Mô tả: {data.description}."
    )
    if data.attributes:
        attrs = ", ".join([f"{k}: {v}" for k, v in data.attributes.items()])
        content += f" Thông số kỹ thuật: {attrs}."

    metadata = {
        "category": data.category,
        "price": str(data.price),
        "id": data.product_id
    }

    # Đưa vào Background Task để không block response
    def _do_vectorize():
        try:
            consultant = get_consultant()
            consultant.add_product_to_knowledge_base(data.product_id, content, metadata)
        except Exception as e:
            logger.error(f"Background vectorize failed: {e}")

    background_tasks.add_task(_do_vectorize)

    return {
        "status": "success",
        "message": f"Product {data.product_id} ({data.name}) queued for vectorization."
    }


@app.get("/api/chat")
async def chat_consultant(query: str):
    """
    RAG Chatbot: Tư vấn sản phẩm cho khách hàng.
    Tìm sản phẩm liên quan (Similarity Search) → Tạo câu trả lời tư vấn.
    
    Example: GET /api/chat?query=tôi muốn mua laptop gaming tầm 30 triệu
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="Vui lòng nhập câu hỏi.")

    try:
        consultant = get_consultant()
        answer = consultant.get_advice(query)
        return {"query": query, "answer": answer}
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/grounded")
async def chat_consultant_grounded(req: GroundedChatRequest):
    """
    Grounded Chat: nhận context sản phẩm đã qua hard-filter từ Django ORM,
    sau đó chỉ sinh câu trả lời dựa trên context này để tránh hallucination.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Vui lòng nhập câu hỏi.")

    try:
        consultant = get_consultant()
        answer = consultant.get_grounded_advice(
            query=req.query,
            context_products=req.context_products,
            constraints=req.constraints or {}
        )
        return {
            "query": req.query,
            "answer": answer,
            "context_size": len(req.context_products),
        }
    except Exception as e:
        logger.error(f"Grounded chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/predict")
async def predict_next_product(request: PredictRequest):
    """
    Deep Learning Prediction: Dự đoán sản phẩm khách hàng sẽ mua tiếp theo.
    
    Input: Danh sách product IDs mà khách đã xem/mua.
    Output: Top-k sản phẩm có xác suất cao nhất.
    
    Example: POST /api/predict
    Body: {"product_ids": [10, 15, 20], "top_k": 5}
    """
    if not request.product_ids:
        raise HTTPException(status_code=400, detail="Vui lòng cung cấp danh sách product IDs.")

    model = get_dl_model()
    if model is None:
        return {
            "product_ids": request.product_ids,
            "predictions": [],
            "message": "⚠️ Deep Learning model chưa sẵn sàng. Đang sử dụng dữ liệu giả lập."
        }

    try:
        from dl_model.behavior_model import predict_next_item
        predictions = predict_next_item(model, request.product_ids, top_k=request.top_k)
        return {
            "product_ids": request.product_ids,
            "predictions": predictions,
            "message": f"Dự đoán top {request.top_k} sản phẩm tiếp theo."
        }
    except Exception as e:
        logger.error(f"Predict error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def vector_db_stats():
    """Thống kê Vector Database (ChromaDB)."""
    try:
        consultant = get_consultant()
        stats = consultant.get_collection_stats()
        return {"status": "ok", "vector_db": stats}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "TechShop AI Service",
        "components": {
            "rag_chatbot": "ready" if _consultant is not None else "lazy (not loaded yet)",
            "dl_model": "ready" if _dl_model is not None else "lazy (not loaded yet)"
        }
    }
