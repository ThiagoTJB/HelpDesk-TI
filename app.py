
from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)

def conectar():
    return sqlite3.connect("database.db")

def criar_banco():
    banco = conectar()
    banco.execute("""
        CREATE TABLE IF NOT EXISTS chamados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            solicitante TEXT NOT NULL,
            titulo TEXT NOT NULL,
            descricao TEXT NOT NULL,
            prioridade TEXT NOT NULL,
            status TEXT DEFAULT 'Aberto'
        )
    """)
    banco.commit()
    banco.close()

@app.route("/")
def inicio():
    banco = conectar()
    chamados = banco.execute(
        "SELECT * FROM chamados ORDER BY id DESC"
    ).fetchall()
    banco.close()

    return render_template("index.html", chamados=chamados)

@app.route("/cadastrar", methods=["POST"])
def cadastrar():
    solicitante = request.form["solicitante"]
    titulo = request.form["titulo"]
    descricao = request.form["descricao"]
    prioridade = request.form["prioridade"]

    banco = conectar()
    banco.execute("""
        INSERT INTO chamados
        (solicitante, titulo, descricao, prioridade)
        VALUES (?, ?, ?, ?)
    """, (solicitante, titulo, descricao, prioridade))

    banco.commit()
    banco.close()

    return redirect("/")

@app.route("/atualizar/<int:id>", methods=["POST"])
def atualizar(id):
    status = request.form["status"]

    status_validos = ["Aberto", "Em andamento", "Concluído"]

    if status not in status_validos:
        return "Status inválido", 400

    banco = conectar()
    banco.execute(
        "UPDATE chamados SET status = ? WHERE id = ?",
        (status, id)
    )
    banco.commit()
    banco.close()

    return redirect("/")

if __name__ == "__main__":
    criar_banco()
    app.run(debug=True)
