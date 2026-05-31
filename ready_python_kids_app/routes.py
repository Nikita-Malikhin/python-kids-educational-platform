import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for, send_from_directory
from werkzeug.security import generate_password_hash

from models import query
from services import (
    current_user,
    lecture_preview,
    load_blocks,
    login_required,
    parse_blocks_from_form,
    role_required,
    valid_password,
)

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['UPLOAD_FOLDER'] = str(BASE_DIR / UPLOAD_FOLDER)
Path(app.config['UPLOAD_FOLDER']).mkdir(exist_ok=True)


@app.context_processor
def inject_user():
    return {'user': current_user()}


@app.route('/')
def index():
    lectures_count = query('SELECT COUNT(*) AS total FROM lectures', one=True)['total']
    tests_count = query('SELECT COUNT(*) AS total FROM tests', one=True)['total']
    return render_template('index.html', lectures_count=lectures_count, tests_count=tests_count)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        login = request.form['login'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        if not login or not email or not password:
            flash('Заполните все поля.', 'warning')
            return render_template('register.html')
        role = query("SELECT role_id FROM roles WHERE role_name='student'", one=True)
        try:
            query('INSERT INTO users (login, password, email, role_id) VALUES (%s, %s, %s, %s)',
                  (login, generate_password_hash(password), email, role['role_id']), commit=True)
            flash('Регистрация выполнена. Теперь войдите в систему.', 'success')
            return redirect(url_for('login'))
        except psycopg2.errors.UniqueViolation:
            flash('Пользователь с таким логином или email уже существует.', 'danger')
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_value = request.form['login'].strip()
        password = request.form['password']
        user = query('''SELECT u.user_id, u.password, r.role_name
                        FROM users u JOIN roles r ON r.role_id=u.role_id
                        WHERE u.login=%s''', (login_value,), one=True)
        if user and valid_password(user['password'], password):
            session['user_id'] = user['user_id']
            flash('Вы успешно вошли в систему.', 'success')
            return redirect(url_for('dashboard'))
        flash('Неверный логин или пароль.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    user = current_user()

    if user['role_name'] == 'teacher':
        stats = {
            'users': query('SELECT COUNT(*) AS total FROM users', one=True)['total'],
            'students': query("""SELECT COUNT(*) AS total
                                FROM users u JOIN roles r ON r.role_id=u.role_id
                                WHERE r.role_name='student'""", one=True)['total'],
            'lectures': query('SELECT COUNT(*) AS total FROM lectures', one=True)['total'],
            'tests': query('SELECT COUNT(*) AS total FROM tests', one=True)['total'],
            'homework_total': query('SELECT COUNT(*) AS total FROM homework_tasks', one=True)['total'],
            'test_results': query('SELECT COUNT(*) AS total FROM results', one=True)['total'],
            'avg_score': query('SELECT COALESCE(ROUND(AVG(score)), 0)::int AS total FROM results', one=True)['total'],
            'homework_done': query('SELECT COUNT(*) AS total FROM homework_results WHERE is_correct=TRUE', one=True)['total'],
            'lecture_progress': query("""SELECT COUNT(*) AS total
                                         FROM (
                                             SELECT DISTINCT user_id, lecture_id
                                             FROM (
                                                 SELECT r.user_id, t.lecture_id
                                                 FROM results r JOIN tests t ON t.test_id=r.test_id
                                                 UNION
                                                 SELECT hr.user_id, h.lecture_id
                                                 FROM homework_results hr
                                                 JOIN homework_tasks h ON h.homework_id=hr.homework_id
                                                 WHERE hr.is_correct=TRUE
                                             ) progress_rows
                                         ) progress""", one=True)['total'],
        }

        possible_lecture_progress = stats['students'] * stats['lectures']
        possible_test_progress = stats['students'] * stats['tests']
        possible_homework_progress = stats['students'] * stats['homework_total']

        stats['lecture_progress_percent'] = round(stats['lecture_progress'] / possible_lecture_progress * 100) if possible_lecture_progress else 0
        stats['test_progress_percent'] = round(stats['test_results'] / possible_test_progress * 100) if possible_test_progress else 0
        stats['homework_progress_percent'] = round(stats['homework_done'] / possible_homework_progress * 100) if possible_homework_progress else 0

        return render_template('teacher_dashboard.html', stats=stats)

    results = query('''SELECT r.score, r.passed_at, t.title AS test_title, l.title AS lecture_title
                       FROM results r JOIN tests t ON t.test_id=r.test_id
                       JOIN lectures l ON l.lecture_id=t.lecture_id
                       WHERE r.user_id=%s ORDER BY r.passed_at DESC''', (user['user_id'],))
    homework_results = query('''SELECT hr.*, h.title, h.level, l.title AS lecture_title
                                FROM homework_results hr JOIN homework_tasks h ON h.homework_id=hr.homework_id
                                JOIN lectures l ON l.lecture_id=h.lecture_id
                                WHERE hr.user_id=%s ORDER BY hr.submitted_at DESC''', (user['user_id'],))

    total_lectures = query('SELECT COUNT(*) AS total FROM lectures', one=True)['total']
    completed_lectures = query("""SELECT COUNT(*) AS total
                                  FROM (
                                      SELECT DISTINCT lecture_id
                                      FROM (
                                          SELECT t.lecture_id
                                          FROM results r JOIN tests t ON t.test_id=r.test_id
                                          WHERE r.user_id=%s
                                          UNION
                                          SELECT h.lecture_id
                                          FROM homework_results hr
                                          JOIN homework_tasks h ON h.homework_id=hr.homework_id
                                          WHERE hr.user_id=%s AND hr.is_correct=TRUE
                                      ) completed
                                  ) lectures_completed""",
                               (user['user_id'], user['user_id']), one=True)['total']

    total_homework = query('SELECT COUNT(*) AS total FROM homework_tasks', one=True)['total']
    completed_homework = query('SELECT COUNT(*) AS total FROM homework_results WHERE user_id=%s AND is_correct=TRUE',
                               (user['user_id'],), one=True)['total']

    completed_tests = query('SELECT COUNT(*) AS total FROM results WHERE user_id=%s',
                            (user['user_id'],), one=True)['total']
    total_tests = query('SELECT COUNT(*) AS total FROM tests', one=True)['total']

    progress = {
        'completed_lectures': completed_lectures,
        'total_lectures': total_lectures,
        'lecture_percent': round(completed_lectures / total_lectures * 100) if total_lectures else 0,
        'completed_homework': completed_homework,
        'total_homework': total_homework,
        'homework_percent': round(completed_homework / total_homework * 100) if total_homework else 0,
        'completed_tests': completed_tests,
        'total_tests': total_tests,
        'test_percent': round(completed_tests / total_tests * 100) if total_tests else 0,
    }

    return render_template('student_dashboard.html', results=results, homework_results=homework_results, progress=progress)


@app.route('/lectures')
@login_required
def lectures():
    items = query('''SELECT l.*, u.login AS author_login,
                    (SELECT COUNT(*) FROM tests t WHERE t.lecture_id=l.lecture_id) AS tests_count,
                    (SELECT COUNT(*) FROM homework_tasks h WHERE h.lecture_id=l.lecture_id) AS homework_count
                    FROM lectures l JOIN users u ON u.user_id=l.author_id ORDER BY l.lecture_id''')
    for item in items:
        item['preview'] = lecture_preview(item.get('content'))
    return render_template('lectures.html', lectures=items)


@app.route('/lectures/<int:lecture_id>')
@login_required
def lecture_detail(lecture_id):
    lecture = query('SELECT * FROM lectures WHERE lecture_id=%s', (lecture_id,), one=True)
    if not lecture:
        flash('Лекция не найдена.', 'danger')
        return redirect(url_for('lectures'))

    tests = query('SELECT * FROM tests WHERE lecture_id=%s ORDER BY test_id', (lecture_id,))
    homework = query("SELECT * FROM homework_tasks WHERE lecture_id=%s ORDER BY CASE level WHEN 'Junior' THEN 1 WHEN 'Middle' THEN 2 ELSE 3 END, homework_id", (lecture_id,))

    homework_results = {}
    user = current_user()
    if user and user['role_name'] == 'student':
        rows = query('''SELECT hr.*
                        FROM homework_results hr
                        JOIN homework_tasks h ON h.homework_id=hr.homework_id
                        WHERE h.lecture_id=%s AND hr.user_id=%s''',
                     (lecture_id, user['user_id']))
        homework_results = {row['homework_id']: row for row in rows}

    return render_template(
        'lecture_detail.html',
        lecture=lecture,
        blocks=load_blocks(lecture['content']),
        tests=tests,
        homework=homework,
        homework_results=homework_results
    )


@app.route('/uploads/<path:filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/tests/<int:test_id>', methods=['GET', 'POST'])
@login_required
@role_required('student')
def take_test(test_id):
    test = query('SELECT * FROM tests WHERE test_id=%s', (test_id,), one=True)
    questions = query('SELECT * FROM questions WHERE test_id=%s ORDER BY question_id', (test_id,))
    for question in questions:
        question['answers'] = query('SELECT * FROM answers WHERE question_id=%s ORDER BY answer_id', (question['question_id'],))
    feedback = []
    score = None
    if request.method == 'POST':
        total = len(questions)
        correct = 0
        for question in questions:
            selected = request.form.get(f'q_{question["question_id"]}')
            chosen = None
            if selected:
                chosen = query('SELECT * FROM answers WHERE answer_id=%s', (selected,), one=True)
                if chosen and chosen['is_correct']:
                    correct += 1
            right = next((a for a in question['answers'] if a['is_correct']), None)
            feedback.append({'question': question, 'chosen': chosen, 'right': right, 'ok': bool(chosen and chosen['is_correct'])})
        score = round(correct / total * 100) if total else 0
        query('''INSERT INTO results (user_id, test_id, score) VALUES (%s, %s, %s)
                 ON CONFLICT (user_id, test_id) DO UPDATE SET score=EXCLUDED.score, passed_at=CURRENT_TIMESTAMP''',
              (session['user_id'], test_id, score), commit=True)
    return render_template('test.html', test=test, questions=questions, feedback=feedback, score=score)


@app.route('/homework/<int:homework_id>', methods=['POST'])
@login_required
@role_required('student')
def submit_homework(homework_id):
    task = query(
        'SELECT * FROM homework_tasks WHERE homework_id=%s',
        (homework_id,),
        one=True
    )

    if not task:
        flash('Домашнее задание не найдено.', 'danger')
        return redirect(url_for('lectures'))

    answer = request.form.get('answer', '').strip()
    ok = answer.lower().replace(' ', '') == task['expected_answer'].lower().replace(' ', '')

    query(
        '''
        INSERT INTO homework_results (homework_id, user_id, answer, is_correct)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (homework_id, user_id)
        DO UPDATE SET
            answer = EXCLUDED.answer,
            is_correct = EXCLUDED.is_correct,
            submitted_at = CURRENT_TIMESTAMP
        ''',
        (homework_id, session['user_id'], answer, ok),
        commit=True
    )

    status = 'correct' if ok else 'wrong'
    return redirect(url_for('lecture_detail', lecture_id=task['lecture_id'], homework=homework_id, status=status))


@app.route('/teacher/lectures/new', methods=['GET', 'POST'])
@login_required
@role_required('teacher')
def new_lecture():
    if request.method == 'POST':
        lecture = query(
            'INSERT INTO lectures (title, content, file_path, author_id) VALUES (%s, %s, %s, %s) RETURNING lecture_id',
            (request.form['title'], parse_blocks_from_form(request, app.config['UPLOAD_FOLDER']), None, session['user_id']),
            one=True
        )
        lecture_id = lecture['lecture_id']

        test_title = request.form.get('test_title', '').strip()
        if test_title:
            test = query(
                'INSERT INTO tests (lecture_id, title, description) VALUES (%s,%s,%s) RETURNING test_id',
                (lecture_id, test_title, request.form.get('test_description', '').strip()),
                one=True
            )

            q_count = int(request.form.get('questions_count', 0) or 0)
            for qi in range(q_count):
                q_text = request.form.get(f'question_{qi}', '').strip()
                if not q_text:
                    continue
                q = query(
                    'INSERT INTO questions (test_id, question_text) VALUES (%s,%s) RETURNING question_id',
                    (test['test_id'], q_text),
                    one=True
                )
                correct_index = request.form.get(f'correct_{qi}')
                for ai in range(4):
                    a_text = request.form.get(f'answer_{qi}_{ai}', '').strip()
                    if a_text:
                        query(
                            'INSERT INTO answers (question_id, answer_text, is_correct, hint) VALUES (%s,%s,%s,%s)',
                            (q['question_id'], a_text, str(ai) == correct_index, request.form.get(f'hint_{qi}_{ai}', '').strip()),
                            commit=True
                        )

        for level in ['Junior', 'Middle', 'Senior']:
            title = request.form.get(f'{level}_title', '').strip()
            description = request.form.get(f'{level}_description', '').strip()
            expected = request.form.get(f'{level}_answer', '').strip()
            if title and description and expected:
                query(
                    'INSERT INTO homework_tasks (lecture_id, level, title, description, expected_answer) VALUES (%s,%s,%s,%s,%s)',
                    (lecture_id, level, title, description, expected),
                    commit=True
                )

        flash('Учебный материал добавлен.', 'success')
        return redirect(url_for('lecture_detail', lecture_id=lecture_id))
    return render_template('lecture_form.html', lecture=None, blocks=[])


@app.route('/teacher/lectures/<int:lecture_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('teacher')
def edit_lecture(lecture_id):
    lecture = query('SELECT * FROM lectures WHERE lecture_id=%s', (lecture_id,), one=True)
    if request.method == 'POST':
        query('UPDATE lectures SET title=%s, content=%s WHERE lecture_id=%s',
              (request.form['title'], parse_blocks_from_form(request, app.config['UPLOAD_FOLDER']), lecture_id), commit=True)
        flash('Учебный материал обновлён.', 'success')
        return redirect(url_for('lecture_detail', lecture_id=lecture_id))
    return render_template('lecture_form.html', lecture=lecture, blocks=load_blocks(lecture['content']))



@app.route('/teacher/lectures/<int:lecture_id>/delete', methods=['POST'])
@login_required
@role_required('teacher')
def delete_lecture(lecture_id):
    lecture = query('SELECT lecture_id FROM lectures WHERE lecture_id=%s', (lecture_id,), one=True)
    if not lecture:
        flash('Лекция не найдена.', 'danger')
        return redirect(url_for('lectures'))

    query('DELETE FROM lectures WHERE lecture_id=%s', (lecture_id,), commit=True)
    flash('Лекция удалена.', 'success')
    return redirect(url_for('lectures'))


@app.route('/teacher/tests/new', methods=['GET', 'POST'])
@login_required
@role_required('teacher')
def new_test():
    lectures = query('SELECT lecture_id, title FROM lectures ORDER BY title')
    if request.method == 'POST':
        test = query('INSERT INTO tests (lecture_id, title, description) VALUES (%s,%s,%s) RETURNING test_id',
                     (request.form['lecture_id'], request.form['title'], request.form['description']), one=True)
        q_count = int(request.form.get('questions_count', 0) or 0)
        for qi in range(q_count):
            q_text = request.form.get(f'question_{qi}', '').strip()
            if not q_text:
                continue
            q = query('INSERT INTO questions (test_id, question_text) VALUES (%s,%s) RETURNING question_id',
                      (test['test_id'], q_text), one=True)
            correct_index = request.form.get(f'correct_{qi}')
            for ai in range(4):
                a_text = request.form.get(f'answer_{qi}_{ai}', '').strip()
                if a_text:
                    query('INSERT INTO answers (question_id, answer_text, is_correct, hint) VALUES (%s,%s,%s,%s)',
                          (q['question_id'], a_text, str(ai) == correct_index, request.form.get(f'hint_{qi}_{ai}', '').strip()), commit=True)
        flash('Полноценный тест с вопросами и вариантами ответов добавлен.', 'success')
        return redirect(url_for('lecture_detail', lecture_id=request.form['lecture_id']))
    return render_template('test_form.html', lectures=lectures)



@app.route('/teacher/tests/<int:test_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('teacher')
def edit_test(test_id):
    test = query('SELECT * FROM tests WHERE test_id=%s', (test_id,), one=True)
    if not test:
        flash('Тест не найден.', 'danger')
        return redirect(url_for('lectures'))

    lectures = query('SELECT lecture_id, title FROM lectures ORDER BY title')

    if request.method == 'POST':
        lecture_id = request.form['lecture_id']
        query('UPDATE tests SET lecture_id=%s, title=%s, description=%s WHERE test_id=%s',
              (lecture_id, request.form['title'], request.form['description'], test_id), commit=True)

        query('DELETE FROM questions WHERE test_id=%s', (test_id,), commit=True)

        q_count = int(request.form.get('questions_count', 0) or 0)
        for qi in range(q_count):
            q_text = request.form.get(f'question_{qi}', '').strip()
            if not q_text:
                continue
            q = query('INSERT INTO questions (test_id, question_text) VALUES (%s,%s) RETURNING question_id',
                      (test_id, q_text), one=True)
            correct_index = request.form.get(f'correct_{qi}')
            for ai in range(4):
                a_text = request.form.get(f'answer_{qi}_{ai}', '').strip()
                if a_text:
                    query('INSERT INTO answers (question_id, answer_text, is_correct, hint) VALUES (%s,%s,%s,%s)',
                          (q['question_id'], a_text, str(ai) == correct_index,
                           request.form.get(f'hint_{qi}_{ai}', '').strip()), commit=True)

        flash('Тест обновлён.', 'success')
        return redirect(url_for('lecture_detail', lecture_id=lecture_id))

    questions = query('SELECT * FROM questions WHERE test_id=%s ORDER BY question_id', (test_id,))
    for q in questions:
        q['answers'] = query('SELECT * FROM answers WHERE question_id=%s ORDER BY answer_id', (q['question_id'],))

    return render_template('test_form.html', lectures=lectures, test=test, questions=questions)



@app.route('/teacher/tests/<int:test_id>/delete', methods=['POST'])
@login_required
@role_required('teacher')
def delete_test(test_id):
    test = query('SELECT lecture_id FROM tests WHERE test_id=%s', (test_id,), one=True)
    if not test:
        flash('Тест не найден.', 'danger')
        return redirect(url_for('lectures'))

    query('DELETE FROM tests WHERE test_id=%s', (test_id,), commit=True)
    flash('Тест удалён.', 'success')
    return redirect(url_for('lecture_detail', lecture_id=test['lecture_id']))


@app.route('/teacher/homework/new', methods=['GET', 'POST'])
@login_required
@role_required('teacher')
def new_homework():
    lectures = query('SELECT lecture_id, title FROM lectures ORDER BY title')
    if request.method == 'POST':
        for level in ['Junior', 'Middle', 'Senior']:
            title = request.form.get(f'{level}_title', '').strip()
            description = request.form.get(f'{level}_description', '').strip()
            expected = request.form.get(f'{level}_answer', '').strip()
            if title and description and expected:
                query('INSERT INTO homework_tasks (lecture_id, level, title, description, expected_answer) VALUES (%s,%s,%s,%s,%s)',
                      (request.form['lecture_id'], level, title, description, expected), commit=True)
        flash('Домашнее задание по уровням добавлено.', 'success')
        return redirect(url_for('lecture_detail', lecture_id=request.form['lecture_id']))
    return render_template('homework_form.html', lectures=lectures)



@app.route('/teacher/homework/<int:lecture_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('teacher')
def edit_homework(lecture_id):
    lecture = query('SELECT * FROM lectures WHERE lecture_id=%s', (lecture_id,), one=True)
    if not lecture:
        flash('Лекция не найдена.', 'danger')
        return redirect(url_for('lectures'))

    lectures = query('SELECT lecture_id, title FROM lectures ORDER BY title')

    if request.method == 'POST':
        new_lecture_id = request.form['lecture_id']
        query('DELETE FROM homework_tasks WHERE lecture_id=%s', (lecture_id,), commit=True)
        for level in ['Junior', 'Middle', 'Senior']:
            title = request.form.get(f'{level}_title', '').strip()
            description = request.form.get(f'{level}_description', '').strip()
            expected = request.form.get(f'{level}_answer', '').strip()
            if title and description and expected:
                query('INSERT INTO homework_tasks (lecture_id, level, title, description, expected_answer) VALUES (%s,%s,%s,%s,%s)',
                      (new_lecture_id, level, title, description, expected), commit=True)
        flash('Домашнее задание обновлено.', 'success')
        return redirect(url_for('lecture_detail', lecture_id=new_lecture_id))

    rows = query('SELECT * FROM homework_tasks WHERE lecture_id=%s', (lecture_id,))
    homework_by_level = {row['level']: row for row in rows}
    return render_template('homework_form.html', lectures=lectures, lecture=lecture, homework_by_level=homework_by_level)



@app.route('/teacher/homework/<int:lecture_id>/delete', methods=['POST'])
@login_required
@role_required('teacher')
def delete_homework(lecture_id):
    lecture = query('SELECT lecture_id FROM lectures WHERE lecture_id=%s', (lecture_id,), one=True)
    if not lecture:
        flash('Лекция не найдена.', 'danger')
        return redirect(url_for('lectures'))

    query('DELETE FROM homework_tasks WHERE lecture_id=%s', (lecture_id,), commit=True)
    flash('Домашнее задание удалено.', 'success')
    return redirect(url_for('lecture_detail', lecture_id=lecture_id))


@app.route('/teacher/results')
@login_required
@role_required('teacher')
def teacher_results():
    items = query('''SELECT u.login, u.email, t.title AS test_title, l.title AS lecture_title, r.score, r.passed_at
                     FROM results r JOIN users u ON u.user_id=r.user_id
                     JOIN tests t ON t.test_id=r.test_id JOIN lectures l ON l.lecture_id=t.lecture_id
                     ORDER BY r.passed_at DESC''')
    hw = query('''SELECT u.login, h.level, h.title, hr.answer, hr.is_correct, hr.submitted_at, l.title AS lecture_title
                  FROM homework_results hr JOIN homework_tasks h ON h.homework_id=hr.homework_id
                  JOIN users u ON u.user_id=hr.user_id JOIN lectures l ON l.lecture_id=h.lecture_id
                  ORDER BY hr.submitted_at DESC''')
    return render_template('teacher_results.html', results=items, homework_results=hw)


@app.route('/teacher/users')
@login_required
@role_required('teacher')
def users_list():
    items = query('''SELECT u.user_id, u.login, u.email, r.role_name
                     FROM users u JOIN roles r ON r.role_id=u.role_id ORDER BY u.user_id''')
    return render_template('users.html', users=items)



@app.route('/teacher/users/<int:user_id>/delete', methods=['POST'])
@login_required
@role_required('teacher')
def delete_user(user_id):
    if session.get('user_id') == user_id:
        flash('Нельзя удалить текущего пользователя.', 'warning')
        return redirect(url_for('users_list'))

    user_to_delete = query('SELECT user_id, login FROM users WHERE user_id=%s', (user_id,), one=True)
    if not user_to_delete:
        flash('Пользователь не найден.', 'danger')
        return redirect(url_for('users_list'))

    query('DELETE FROM lectures WHERE author_id=%s', (user_id,), commit=True)
    query('DELETE FROM users WHERE user_id=%s', (user_id,), commit=True)
    flash(f"Пользователь {user_to_delete['login']} удален.", 'success')
    return redirect(url_for('users_list'))

@app.route('/teacher/users/new-admin', methods=['GET', 'POST'])
@login_required
@role_required('teacher')
def new_admin():
    if request.method == 'POST':
        login_value = request.form.get('login', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not login_value or not email or not password:
            flash('Заполните логин, почту и пароль.', 'warning')
            return render_template('admin_form.html')

        teacher_role = query("SELECT role_id FROM roles WHERE role_name='teacher'", one=True)
        if not teacher_role:
            query("INSERT INTO roles (role_name) VALUES ('teacher')", commit=True)
            teacher_role = query("SELECT role_id FROM roles WHERE role_name='teacher'", one=True)

        try:
            query(
                'INSERT INTO users (login, password, email, role_id) VALUES (%s, %s, %s, %s)',
                (login_value, generate_password_hash(password), email, teacher_role['role_id']),
                commit=True
            )
            flash('Администратор добавлен.', 'success')
            return redirect(url_for('users_list'))
        except psycopg2.errors.UniqueViolation:
            flash('Пользователь с таким логином или почтой уже существует.', 'danger')

    return render_template('admin_form.html')
