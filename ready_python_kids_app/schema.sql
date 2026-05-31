CREATE DATABASE informatics_site;
\c informatics_site

CREATE TABLE IF NOT EXISTS roles (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    login VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    role_id INT NOT NULL REFERENCES roles(role_id)
);

CREATE TABLE IF NOT EXISTS lectures (
    lecture_id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    file_path VARCHAR(255),
    author_id INT NOT NULL REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS tests (
    test_id SERIAL PRIMARY KEY,
    lecture_id INT NOT NULL REFERENCES lectures(lecture_id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS questions (
    question_id SERIAL PRIMARY KEY,
    test_id INT NOT NULL REFERENCES tests(test_id) ON DELETE CASCADE,
    question_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS answers (
    answer_id SERIAL PRIMARY KEY,
    question_id INT NOT NULL REFERENCES questions(question_id) ON DELETE CASCADE,
    answer_text TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS results (
    result_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    test_id INT NOT NULL REFERENCES tests(test_id) ON DELETE CASCADE,
    score INT NOT NULL,
    passed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_user_test UNIQUE (user_id, test_id)
);

INSERT INTO roles (role_name) VALUES ('student') ON CONFLICT (role_name) DO NOTHING;
INSERT INTO roles (role_name) VALUES ('teacher') ON CONFLICT (role_name) DO NOTHING;

INSERT INTO lectures (title, content, file_path, author_id)
SELECT 'Введение в Python', 'Python — простой язык программирования, подходящий для первого знакомства с алгоритмами. В этом уроке рассматриваются переменные, вывод текста и базовые команды.', NULL, user_id
FROM users WHERE login='teacher1'
ON CONFLICT DO NOTHING;

INSERT INTO tests (lecture_id, title, description)
SELECT lecture_id, 'Итоговый тест по введению в Python', 'Проверка базовых знаний по первому уроку.'
FROM lectures WHERE title='Введение в Python'
ON CONFLICT DO NOTHING;

INSERT INTO questions (test_id, question_text)
SELECT test_id, 'Какая команда используется для вывода текста в Python?'
FROM tests WHERE title='Итоговый тест по введению в Python'
ON CONFLICT DO NOTHING;

INSERT INTO answers (question_id, answer_text, is_correct)
SELECT q.question_id, v.answer_text, v.is_correct
FROM questions q
JOIN tests t ON t.test_id=q.test_id
CROSS JOIN (VALUES ('print()', TRUE), ('echo()', FALSE), ('write()', FALSE)) AS v(answer_text,is_correct)
WHERE t.title='Итоговый тест по введению в Python'
ON CONFLICT DO NOTHING;

ALTER TABLE answers ADD COLUMN IF NOT EXISTS hint TEXT;

CREATE TABLE IF NOT EXISTS homework_tasks (
    homework_id SERIAL PRIMARY KEY,
    lecture_id INT NOT NULL REFERENCES lectures(lecture_id) ON DELETE CASCADE,
    level VARCHAR(20) NOT NULL CHECK (level IN ('Junior','Middle','Senior')),
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    expected_answer VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS homework_results (
    homework_result_id SERIAL PRIMARY KEY,
    homework_id INT NOT NULL REFERENCES homework_tasks(homework_id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    answer TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_user_homework UNIQUE (homework_id, user_id)
);
