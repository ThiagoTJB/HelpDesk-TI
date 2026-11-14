
from flask import Flask, render_template, request, redirect, flash
import sqlite3

app = Flask(__name__)

app.secret_key = "helpdesk-ti-chave"


# Conexão com o banco de dados
def conectar():
    return sqlite3.connect("database.db")


# Criar banco de dados e verificar colunas
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

    # Verificar se a coluna de data existe
    colunas = banco.execute(
        "PRAGMA table_info(chamados)"
    ).fetchall()

    nomes_colunas = [coluna[1] for coluna in colunas]

    if "data_abertura" not in nomes_colunas:
        banco.execute("""
            ALTER TABLE chamados
            ADD COLUMN data_abertura TEXT
        """)

    # Preencher data dos chamados antigos
    banco.execute("""
        UPDATE chamados
        SET data_abertura = strftime(
            '%d/%m/%Y %H:%M', 'now', 'localtime'
        )
        WHERE data_abertura IS NULL
    """)
    # Criar tabela de histórico
    banco.execute("""
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chamado_id INTEGER,
            acao TEXT NOT NULL,
            descricao TEXT NOT NULL,
            data_hora TEXT NOT NULL
        )
    """)
    banco.commit()
    banco.close()


# Página inicial e painel administrativo
@app.route("/")
def inicio():
    banco = conectar()

    # Filtros
    status = request.args.get("status", "")
    prioridade = request.args.get("prioridade", "")
    busca = request.args.get("busca", "")

    sql = "SELECT * FROM chamados WHERE 1=1"
    parametros = []

  
    if status:
        sql += " AND status = ?"
        parametros.append(status)

    if prioridade:
        sql += " AND prioridade = ?"
        parametros.append(prioridade)

    if busca:
        sql += """
            AND (
                solicitante LIKE ?
                OR titulo LIKE ?
                OR descricao LIKE ?
            )
        """

        parametros.extend([
            f"%{busca}%",
            f"%{busca}%",
            f"%{busca}%"
        ])


    sql += " ORDER BY id DESC"


    

    chamados = banco.execute(sql, parametros).fetchall()

    

    # Indicadores do painel
    total = banco.execute(
        "SELECT COUNT(*) FROM chamados"
    ).fetchone()[0]

    abertos = banco.execute(
        "SELECT COUNT(*) FROM chamados WHERE status = 'Aberto'"
    ).fetchone()[0]

    andamento = banco.execute(
        "SELECT COUNT(*) FROM chamados WHERE status = 'Em andamento'"
    ).fetchone()[0]

    concluidos = banco.execute(
        "SELECT COUNT(*) FROM chamados WHERE status = 'Concluído'"
    ).fetchone()[0]

    banco.close()

    return render_template(
        "index.html",
        chamados=chamados,
        total=total,
        abertos=abertos,
        andamento=andamento,
        concluidos=concluidos,
        status_selecionado=status,
        prioridade_selecionada=prioridade
    )


# Cadastrar chamado
@app.route("/cadastrar", methods=["POST"])
def cadastrar():
    solicitante = request.form["solicitante"].strip()
    titulo = request.form["titulo"].strip()
    descricao = request.form["descricao"].strip()
    prioridade = request.form["prioridade"]

    # Validar campos obrigatórios
    if not solicitante or not titulo or not descricao:
        flash(
            "Preencha todos os campos obrigatórios!",
            "erro"
        )
        return redirect("/")

    # Validar prioridade
    prioridades_validas = ["Baixa", "Média", "Alta"]

    if prioridade not in prioridades_validas:
        flash("Prioridade inválida!", "erro")
        return redirect("/")

    banco = conectar()

    banco.execute("""
        INSERT INTO chamados
        (solicitante, titulo, descricao, prioridade, data_abertura)
        VALUES (?, ?, ?, ?, strftime('%d/%m/%Y %H:%M', 'now', 'localtime'))
    """, (solicitante, titulo, descricao, prioridade))

    banco.commit()

    # Registrar cadastro no histórico
    banco.execute("""
        INSERT INTO historico
        (chamado_id, acao, descricao, data_hora)
        VALUES (?, ?, ?, strftime('%d/%m/%Y %H:%M', 'now', 'localtime'))
    """, (
        banco.execute("SELECT last_insert_rowid()").fetchone()[0],
        "Cadastro",
        f"Chamado cadastrado por {solicitante}: {titulo}"
    ))

    banco.commit()
    banco.close()

    flash("Chamado cadastrado com sucesso!", "sucesso")

    return redirect("/")


# Atualizar status
@app.route("/atualizar/<int:id>", methods=["POST"])
def atualizar(id):
    status = request.form["status"]

    status_validos = [
        "Aberto",
        "Em andamento",
        "Concluído"
    ]

    if status not in status_validos:
        return "Status inválido", 400

    banco = conectar()
    # Consultar status anterior
    chamado = banco.execute(
        "SELECT status FROM chamados WHERE id = ?",
        (id,)
    ).fetchone()

    if chamado is None:
        banco.close()
        return "Chamado não encontrado", 404

    status_anterior = chamado[0]

    # Atualizar status
    banco.execute(
        "UPDATE chamados SET status = ? WHERE id = ?",
        (status, id)
    )

    # Registrar alteração no histórico
    if status_anterior != status:
        banco.execute("""
            INSERT INTO historico
            (chamado_id, acao, descricao, data_hora)
            VALUES (?, ?, ?, strftime('%d/%m/%Y %H:%M', 'now', 'localtime'))
        """, (
            id,
            "Alteração de status",
            f"Status alterado de {status_anterior} para {status}"
        ))

    banco.commit()
    banco.close()

    return redirect("/")


# Excluir chamado


@app.route("/excluir/<int:id>", methods=["POST"])
def excluir(id):
    banco = conectar()

    # Buscar todos os dados antes da exclusão
    chamado = banco.execute("""
        SELECT solicitante, titulo, descricao,
               prioridade, status, data_abertura
        FROM chamados
        WHERE id = ?
    """, (id,)).fetchone()

    if chamado is None:
        banco.close()
        return "Chamado não encontrado", 404

    solicitante = chamado[0]
    titulo = chamado[1]
    descricao = chamado[2]
    prioridade = chamado[3]
    status = chamado[4]
    data_abertura = chamado[5]

    # Montar registro completo da exclusão
    detalhes = (
        f"Chamado excluído.\n"
        f"Solicitante: {solicitante}\n"
        f"Título: {titulo}\n"
        f"Descrição: {descricao}\n"
        f"Prioridade: {prioridade}\n"
        f"Status: {status}\n"
        f"Data de abertura: {data_abertura}"
    )

    # Salvar informações no histórico
    banco.execute("""
        INSERT INTO historico
        (chamado_id, acao, descricao, data_hora)
        VALUES (?, ?, ?, strftime('%d/%m/%Y %H:%M', 'now', 'localtime'))
    """, (id, "Exclusão", detalhes))

    # Excluir chamado
    banco.execute(
        "DELETE FROM chamados WHERE id = ?",
        (id,)
    )

    banco.commit()
    banco.close()

    return redirect("/")


# Editar chamado
@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    banco = conectar()

    if request.method == "POST":
        solicitante = request.form["solicitante"].strip()
        titulo = request.form["titulo"].strip()
        descricao = request.form["descricao"].strip()
        prioridade = request.form["prioridade"]

        # Validar campos obrigatórios
        if not solicitante or not titulo or not descricao:
            banco.close()
            flash("Preencha todos os campos obrigatórios!", "erro")
            return redirect(f"/editar/{id}")

        prioridades_validas = ["Baixa", "Média", "Alta"]

        if prioridade not in prioridades_validas:
            banco.close()
            flash("Prioridade inválida!", "erro")
            return redirect(f"/editar/{id}")
        # Atualizar chamado
        banco.execute("""
            UPDATE chamados
            SET solicitante = ?,
                titulo = ?,
                descricao = ?,
                prioridade = ?
            WHERE id = ?
        """, (solicitante, titulo, descricao, prioridade, id))

        # Registrar edição no histórico
        banco.execute("""
            INSERT INTO historico
            (chamado_id, acao, descricao, data_hora)
            VALUES (?, ?, ?, strftime('%d/%m/%Y %H:%M', 'now', 'localtime'))
        """, (
            id,
            "Edição",
            f"Chamado editado. Solicitante: {solicitante}, título: {titulo}, prioridade: {prioridade}"
        ))

        banco.commit()
        banco.close()

        flash("Chamado atualizado com sucesso!", "sucesso")
        return redirect("/")

    chamado = banco.execute(
        "SELECT * FROM chamados WHERE id = ?",
        (id,)
    ).fetchone()

    banco.close()

    if chamado is None:
        return "Chamado não encontrado", 404

    return render_template("editar.html", chamado=chamado)

# Visualizar histórico de um chamado
@app.route("/historico/<int:id>")
def historico(id):
    banco = conectar()

    # Buscar chamado
    chamado = banco.execute(
        "SELECT * FROM chamados WHERE id = ?",
        (id,)
    ).fetchone()

    if chamado is None:
        banco.close()
        return "Chamado não encontrado", 404

    # Buscar registros do histórico
    registros = banco.execute("""
        SELECT * FROM historico
        WHERE chamado_id = ?
        ORDER BY id DESC
    """, (id,)).fetchall()

    banco.close()

    return render_template(
        "historico.html",
        chamado=chamado,
        registros=registros
    )



# Visualizar histórico geral

# Visualizar histórico geral
@app.route("/historico-geral")
def historico_geral():
    banco = conectar()

    busca = request.args.get("busca", "").strip()
    acao = request.args.get("acao", "")

    sql = """
        SELECT historico.*
        FROM historico
        WHERE 1=1
    """

    parametros = []

    if busca:
        sql += """
            AND (
                CAST(historico.chamado_id AS TEXT) LIKE ?
                OR historico.descricao LIKE ?
            )
        """

        parametros.extend([
            f"%{busca}%",
            f"%{busca}%"
        ])

    if acao:
        sql += " AND historico.acao = ?"
        parametros.append(acao)

    sql += " ORDER BY historico.id DESC"

    registros = banco.execute(
        sql, parametros
    ).fetchall()

    banco.close()

    return render_template(
        "historico_geral.html",
        registros=registros,
        busca=busca,
        acao_selecionada=acao
    )


# Executar aplicação
if __name__ == "__main__":
    criar_banco()
    app.run(debug=True)
