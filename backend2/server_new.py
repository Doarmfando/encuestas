"""
Punto de entrada del servidor - Sistema de Encuestas v3 (Proyectos).
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    print("=" * 50)
    print("  Sistema de Encuestas v3")
    print("  http://localhost:5002")
    print("  BD: sistema_encuestas (PostgreSQL)")
    print("  API: /api/projects, /api/dashboard")
    print("=" * 50)
    app.run(debug=False, port=5002)
