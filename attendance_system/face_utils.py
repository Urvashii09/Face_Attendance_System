import numpy as np
import cv2

_face_app = None


def get_face_app():
    """Lazy-load InsightFace FaceAnalysis (ArcFace / buffalo_l model)."""
    global _face_app
    if _face_app is None:
        from insightface.app import FaceAnalysis
        _face_app = FaceAnalysis(
            name='buffalo_l',
            providers=['CPUExecutionProvider']
        )
        _face_app.prepare(ctx_id=0, det_size=(640, 640))
    return _face_app


def extract_embedding(image_bgr):
    """
    Detect the largest face in a BGR image and return its
    (normed_embedding, bbox) or (None, None) if no face found.
    """
    app = get_face_app()
    faces = app.get(image_bgr)
    if not faces:
        return None, None
    # Pick the largest face by bounding-box area
    face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    return face.normed_embedding, face.bbox


def cosine_similarity(a, b):
    """Cosine similarity between two L2-normalised vectors."""
    return float(np.dot(a, b))


def recognize_face(query_embedding, users, threshold=0.45):
    """
    Compare query_embedding against all registered user embeddings.
    Returns (best_matching_user_dict, score) or (None, score).
    """
    best_user = None
    best_score = -1.0

    for user in users:
        score = cosine_similarity(query_embedding, user['embedding'])
        if score > best_score:
            best_score = score
            best_user = user

    if best_score >= threshold:
        return best_user, best_score
    return None, best_score
