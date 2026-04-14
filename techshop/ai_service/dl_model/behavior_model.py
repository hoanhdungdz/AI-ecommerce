"""
Deep Learning Model: Behavior Analysis — Dự đoán sản phẩm khách hàng sẽ mua tiếp theo.

Sử dụng TensorFlow/Keras LSTM Sequence Model:
- Input: Mảng chứa ID các sản phẩm khách đã xem (Sequence)
- Output: ID sản phẩm có xác suất cao nhất

Bao gồm phần tiền xử lý dữ liệu từ Database Django (QuerySet) sang Numpy array.
"""
import os
import logging
import numpy as np

logger = logging.getLogger(__name__)

# Lazy import TensorFlow (nặng, chỉ load khi cần)
tf = None
Sequential = None
Embedding = None
LSTM = None
Dense = None
Dropout = None
pad_sequences = None
to_categorical = None


def _ensure_tensorflow():
    """Lazy load TensorFlow để tránh crash nếu không cài."""
    global tf, Sequential, Embedding, LSTM, Dense, Dropout, pad_sequences, to_categorical
    if tf is not None:
        return True
    try:
        import tensorflow as _tf
        tf = _tf
        from tensorflow.keras.models import Sequential as _Sequential
        from tensorflow.keras.layers import Embedding as _Embedding, LSTM as _LSTM
        from tensorflow.keras.layers import Dense as _Dense, Dropout as _Dropout
        from tensorflow.keras.preprocessing.sequence import pad_sequences as _pad_sequences
        from tensorflow.keras.utils import to_categorical as _to_categorical
        Sequential = _Sequential
        Embedding = _Embedding
        LSTM = _LSTM
        Dense = _Dense
        Dropout = _Dropout
        pad_sequences = _pad_sequences
        to_categorical = _to_categorical
        logger.info("✅ TensorFlow loaded successfully.")
        return True
    except ImportError as e:
        logger.error(f"❌ TensorFlow not installed: {e}")
        return False


# ============================================================
# Phần 1: Tiền xử lý dữ liệu từ Django QuerySet → Numpy Array
# ============================================================
def preprocess_django_data(max_sequence_length=10, vocab_size=1000):
    """
    Chuyển đổi dữ liệu khách hàng từ Django QuerySet thành dạng Numpy array
    cho Sequence Prediction task.
    
    Trong thực tế (với Django):
        from collections import defaultdict
        from shop.models import OrderItem, ViewHistory
        
        # Cách 1: Từ lịch sử mua hàng (OrderItem)
        user_sessions = defaultdict(list)
        for item in OrderItem.objects.select_related('order').order_by('order__created_at'):
            user_sessions[item.order.customer_id].append(item.product_id)
        
        # Cách 2: Từ lịch sử xem sản phẩm (ViewHistory) — dùng cách này tốt hơn
        user_sessions = defaultdict(list)
        for vh in ViewHistory.objects.order_by('viewed_at'):
            user_sessions[vh.customer_id].append(vh.product_id)
    
    Ở đây dùng dữ liệu giả lập để demo.
    """
    if not _ensure_tensorflow():
        return None, None

    try:
        # ========================================================
        # GIẢ LẬP dữ liệu từ Database Django.
        # Trong production, thay bằng QuerySet thật (xem docstring ở trên).
        # ========================================================
        # Format: {customer_id: [product_id_1, product_id_2, ...]}
        # Thứ tự theo thời gian (sản phẩm xem/mua trước → sau)
        user_sessions = {
            1: [10, 15, 20, 25, 30, 35],       # Khách thích xem Laptop
            2: [5, 10, 12, 10, 15, 30, 20],     # Khách xem đa dạng
            3: [100, 101, 102, 100, 103],        # Khách thích Phụ kiện
            4: [50, 51, 52, 53, 54, 55, 56],     # Khách mua Quần áo
            5: [10, 100, 50, 15, 101, 51, 20],   # Mixed
            6: [25, 30, 35, 25, 30, 35, 25],     # Repeat pattern
            7: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],  # Sequential
            8: [200, 201, 202, 203, 204],         # Premium products
        }

    except Exception as e:
        logger.error(f"Lỗi truy xuất Django Models: {e}")
        return None, None

    # ========================================================
    # Chuẩn bị Sequence: Sliding Window
    # Từ [A, B, C, D] tạo ra:
    #   X=[A]      → Y=B
    #   X=[A,B]    → Y=C  
    #   X=[A,B,C]  → Y=D
    # ========================================================
    sequences = []
    for user_id, items in user_sessions.items():
        for i in range(1, len(items)):
            seq = items[:i + 1]  # [X1, X2, ..., Y]
            sequences.append(seq)

    # Tách X (input) và y (target)
    X, y = [], []
    for seq in sequences:
        X.append(seq[:-1])  # Tất cả phần tử trừ cuối
        y.append(seq[-1])   # Phần tử cuối = sản phẩm cần predict

    # Padding X: Đệm bằng 0 ở đầu cho cùng độ dài
    X = pad_sequences(X, maxlen=max_sequence_length, padding='pre')

    # Chuyển Y thành One-Hot Encoding
    y = to_categorical(y, num_classes=vocab_size)

    logger.info(f"📊 Preprocessed: X shape={X.shape}, y shape={y.shape}, "
                f"{len(sequences)} sequences từ {len(user_sessions)} users.")

    return np.array(X), np.array(y)


# ============================================================
# Phần 2: Xây dựng và Train Model Deep Learning (LSTM)
# ============================================================
def build_and_train_model(train=False):
    """
    Xây dựng model LSTM cho Sequence Prediction.
    
    Architecture:
    - Embedding(vocab_size, 64): Chuyển product ID → vector 64 chiều
    - LSTM(128): Học pattern từ chuỗi sản phẩm
    - Dropout(0.2): Tránh overfitting
    - Dense(64, relu): Hidden layer
    - Dense(vocab_size, softmax): Output probability cho mỗi sản phẩm
    
    Args:
        train: Nếu True, train model thực tế. Nếu False, chỉ build + summary.
    """
    if not _ensure_tensorflow():
        return None

    # 1. Hyperparameters
    VOCAB_SIZE = 1000           # Tổng số mặt hàng tối đa (product ID space)
    MAX_SEQUENCE_LENGTH = 10    # Độ dài tối đa chuỗi xem xét
    EMBEDDING_DIM = 64          # Kích thước embedding vector
    EPOCHS = 20
    BATCH_SIZE = 32

    # 2. Tiền xử lý dữ liệu
    X_train, y_train = preprocess_django_data(
        max_sequence_length=MAX_SEQUENCE_LENGTH,
        vocab_size=VOCAB_SIZE
    )

    if X_train is None:
        logger.error("Preprocess Failed.")
        return None

    # 3. Xây dựng Model
    model = Sequential([
        Embedding(
            input_dim=VOCAB_SIZE,
            output_dim=EMBEDDING_DIM,
            input_length=MAX_SEQUENCE_LENGTH,
            name='product_embedding'
        ),
        LSTM(128, return_sequences=False, name='lstm_sequence'),
        Dropout(0.2, name='dropout'),
        Dense(64, activation='relu', name='hidden_layer'),
        Dense(VOCAB_SIZE, activation='softmax', name='output_predictions')
    ])

    # 4. Compile
    model.compile(
        loss='categorical_crossentropy',
        optimizer='adam',
        metrics=['accuracy']
    )

    # 5. Model Summary
    model.summary()

    # 6. Train (nếu được yêu cầu)
    if train:
        logger.info("🏋️ Bắt đầu training model...")
        history = model.fit(
            X_train, y_train,
            epochs=EPOCHS,
            batch_size=BATCH_SIZE,
            validation_split=0.2,
            verbose=1
        )
        logger.info(f"✅ Training hoàn tất. "
                     f"Final accuracy: {history.history['accuracy'][-1]:.4f}")

        # Lưu model
        model_path = "./saved_model/behavior_model.keras"
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        model.save(model_path)
        logger.info(f"💾 Model saved to {model_path}")
    else:
        logger.info("ℹ️ Model built (chưa train). Set train=True để train.")

    return model


def load_or_build_model():
    """Tải model đã train hoặc build mới."""
    if not _ensure_tensorflow():
        return None

    model_path = "./saved_model/behavior_model.keras"
    if os.path.exists(model_path):
        try:
            model = tf.keras.models.load_model(model_path)
            logger.info(f"✅ Model loaded from {model_path}")
            return model
        except Exception as e:
            logger.warning(f"⚠️ Không load được model: {e}. Build mới...")

    return build_and_train_model(train=True)


def predict_next_item(model, user_history, max_sequence_length=10, top_k=5):
    """
    Dự đoán sản phẩm tiếp theo dựa trên lịch sử xem/mua.
    
    Args:
        model: Trained Keras model
        user_history: List[int] — Danh sách product IDs đã xem
        max_sequence_length: Độ dài padding
        top_k: Số lượng gợi ý trả về
    
    Returns:
        List[Dict]: Top-k sản phẩm gợi ý với probability
    """
    if model is None:
        return [{"product_id": 0, "probability": 0.0, "error": "Model chưa sẵn sàng"}]

    if not _ensure_tensorflow():
        return [{"product_id": 0, "probability": 0.0, "error": "TensorFlow not available"}]

    # Padding user history
    input_seq = pad_sequences([user_history], maxlen=max_sequence_length, padding='pre')

    # Predict
    probabilities = model.predict(input_seq, verbose=0)[0]

    # Lấy top-k indices
    top_indices = np.argsort(probabilities)[-top_k:][::-1]

    results = []
    for idx in top_indices:
        if probabilities[idx] > 0.001:  # Chỉ lấy nếu probability đáng kể
            results.append({
                "product_id": int(idx),
                "probability": float(probabilities[idx])
            })

    return results if results else [{"product_id": int(np.argmax(probabilities)),
                                      "probability": float(np.max(probabilities))}]


if __name__ == "__main__":
    # Test script locally
    print("=== Build Model ===")
    trained_model = build_and_train_model(train=True)

    if trained_model:
        print("\n=== Predict ===")
        # Test: Khách hàng đã xem sản phẩm ID [10, 15, 20]
        predictions = predict_next_item(trained_model, [10, 15, 20])
        print("Dự đoán sản phẩm tiếp theo:")
        for pred in predictions:
            print(f"  Product ID: {pred['product_id']}, "
                  f"Xác suất: {pred['probability']:.4f}")
