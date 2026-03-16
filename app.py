import base64
import datetime as dt

import cv2
import numpy as np
from flask import Flask, jsonify, redirect, render_template, request, url_for

''

from database import (
    add_face_sample,
    add_user,
    delete_user,
    get_all_users,
    get_attendance_records,
    get_settings,
    init_db,
    list_users,
    mark_attendance,
    save_settings,
)
from face_utils import extract_embedding, recognize_face

app = Flask(__name__, static_folder='static', template_folder='templates')


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    total_users = len(list_users())
    total_records = len(get_attendance_records())
    return render_template('index.html', total_users=total_users, total_records=total_records)


@app.route('/register', methods=['GET'])
def register():
    users = list_users()
    total_users = len(users)
    total_samples = sum(u[3] for u in users)
    return render_template('register.html', users=users, total_users=total_users, total_samples=total_samples)


@app.route('/attendance')
def attendance():
    total_users = len(list_users())
    today_records = [r for r in get_attendance_records() if r[1] == dt.date.today().isoformat()]
    settings = get_settings()
    return render_template('attendance.html', total_users=total_users, today_count=len(today_records), settings=settings)


@app.route('/records')
def records():
    data = get_attendance_records()
    users = list_users()
    settings = get_settings()
    return render_template('records.html', records=data, users=users, settings=settings)


@app.route('/settings', methods=['GET', 'POST'])
def settings_page():
    if request.method == 'POST':
        check_in  = request.form.get('check_in_time',  '09:00')
        check_out = request.form.get('check_out_time', '17:00')
        save_settings(check_in, check_out)
        return redirect(url_for('settings_page'))
    s = get_settings()
    return render_template('settings.html', settings=s)


# ---------------------------------------------------------------------------
# API – Registration
# ---------------------------------------------------------------------------

@app.route('/api/register', methods=['POST'])
def api_register():
    try:
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        images = data.get('images', [])

        if not name:
            return jsonify({'success': False, 'error': 'Name is required.'})
        if not images:
            return jsonify({'success': False, 'error': 'At least one image is required.'})

        embeddings = []
        for image_data in images:
            try:
                header, encoded = image_data.split(',', 1)
                img_bytes = base64.b64decode(encoded)
            except Exception:
                continue
            img_array = np.frombuffer(img_bytes, np.uint8)
            img_bgr = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if img_bgr is None:
                continue
            embedding, bbox = extract_embedding(img_bgr)
            if embedding is not None:
                embeddings.append(embedding)

        if not embeddings:
            return jsonify({'success': False, 'error': 'No face detected in any captured image. Try better lighting.'})

        user_id = add_user(name)
        for emb in embeddings:
            add_face_sample(user_id, emb)

        return jsonify({
            'success': True,
            'message': f'"{name}" registered with {len(embeddings)} face sample(s)!',
            'user_id': user_id,
            'samples': len(embeddings),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'}), 500


# ---------------------------------------------------------------------------
# API – Recognition / Attendance
# ---------------------------------------------------------------------------

@app.route('/api/recognize', methods=['POST'])
def api_recognize():
    try:
        data = request.get_json(silent=True) or {}
        image_data = data.get('image', '')

        if not image_data:
            return jsonify({'success': False, 'error': 'No image provided.'})

        try:
            header, encoded = image_data.split(',', 1)
            img_bytes = base64.b64decode(encoded)
        except Exception:
            return jsonify({'success': False, 'error': 'Invalid image data.'})

        img_array = np.frombuffer(img_bytes, np.uint8)
        img_bgr = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img_bgr is None:
            return jsonify({'success': False, 'error': 'Could not decode image.'})

        embedding, bbox = extract_embedding(img_bgr)
        if embedding is None:
            return jsonify({'success': False, 'error': 'No face detected.'})

        users = get_all_users()
        if not users:
            return jsonify({'success': False, 'error': 'No users registered yet. Please register first.'})

        match, score = recognize_face(embedding, users)
        if match is None:
            return jsonify({'success': False, 'error': f'Unknown person (confidence: {score:.2f})'})

        # Determine status based on schedule settings
        s = get_settings()
        now_time = dt.datetime.now().strftime('%H:%M')
        check_in_limit  = s.get('check_in_time',  '09:00')
        check_out_limit = s.get('check_out_time', '17:00')
        if now_time <= check_in_limit:
            status = 'on_time'
        elif now_time <= check_out_limit:
            status = 'late'
        else:
            status = 'overtime'

        already_marked = not mark_attendance(match['id'], status=status, check_in_time=now_time)
        return jsonify({
            'success': True,
            'name': match['name'],
            'score': round(score, 3),
            'already_marked': already_marked,
            'status': status,
            'check_in_time': now_time,
            'check_in_limit': check_in_limit,
            'check_out_limit': check_out_limit,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'}), 500


# ---------------------------------------------------------------------------
# API – Delete user
# ---------------------------------------------------------------------------

@app.route('/api/delete_user/<int:user_id>', methods=['DELETE'])
def api_delete_user(user_id):
    delete_user(user_id)
    return jsonify({'success': True})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    init_db()
    print("Starting Attendance System...")
    print("Open http://127.0.0.1:5000 in your browser")
    app.run(debug=True, use_reloader=False)
