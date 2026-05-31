from models import ensure_schema
from routes import app


if __name__ == '__main__':
    ensure_schema()
    app.run(debug=True)
