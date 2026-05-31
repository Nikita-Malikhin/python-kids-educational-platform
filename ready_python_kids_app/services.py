import json
import re
from functools import wraps
from pathlib import Path

from flask import flash, redirect, session, url_for
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from models import query


def current_user():
    if 'user_id' not in session:
        return None
    return query(
        """SELECT u.user_id, u.login, u.email, r.role_name
           FROM users u JOIN roles r ON r.role_id = u.role_id
           WHERE u.user_id=%s""",
        (session['user_id'],),
        one=True
    )


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if 'user_id' not in session:
            flash('Для доступа к разделу необходимо войти в систему.', 'warning')
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped


def role_required(role):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user or user['role_name'] != role:
                flash('Недостаточно прав доступа.', 'danger')
                return redirect(url_for('index'))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def valid_password(saved_password, entered_password):
    if saved_password and (saved_password.startswith('pbkdf2:') or saved_password.startswith('scrypt:')):
        return check_password_hash(saved_password, entered_password)
    return saved_password == entered_password


def parse_blocks_from_form(request_obj, upload_folder):
    blocks = []
    count = int(request_obj.form.get('blocks_count', 0) or 0)
    for i in range(count):
        block_type = request_obj.form.get(f'block_type_{i}')
        if not block_type:
            continue
        block = {'type': block_type}
        if block_type in ('text', 'code'):
            block['content'] = request_obj.form.get(f'block_content_{i}', '').strip()
        elif block_type == 'image':
            file = request_obj.files.get(f'block_image_{i}')
            old_src = request_obj.form.get(f'block_old_src_{i}', '')
            if file and file.filename:
                filename = secure_filename(file.filename)
                file.save(Path(upload_folder) / filename)
                block['src'] = filename
            else:
                block['src'] = old_src
            block['caption'] = request_obj.form.get(f'block_caption_{i}', '').strip()
        blocks.append(block)
    return json.dumps(blocks, ensure_ascii=False)


def load_blocks(content):
    if not content:
        return []
    try:
        data = json.loads(content)
        return data if isinstance(data, list) else [{'type': 'text', 'content': content}]
    except Exception:
        return [{'type': 'text', 'content': content}]


def strip_markup(text):
    return re.sub(r'<[^>]+>', '', text or '')


def lecture_preview(content, limit=180):
    blocks = load_blocks(content)
    text_parts = []
    for block in blocks:
        if block.get('type') == 'text' and block.get('content'):
            text_parts.append(strip_markup(block['content']).replace('\n', ' '))
        elif block.get('type') == 'code' and block.get('content'):
            text_parts.append('Пример кода: ' + strip_markup(block['content']).replace('\n', ' '))
        elif block.get('type') == 'image':
            text_parts.append('Изображение к лекции')
    preview = ' '.join(text_parts).strip()
    if not preview:
        preview = 'Описание материала пока не заполнено.'
    return preview[:limit] + ('...' if len(preview) > limit else '')
