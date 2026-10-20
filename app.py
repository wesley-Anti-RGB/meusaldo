# MeuSaldo: organizador financeiro com HTML, CSS e Python
# Usa somente a biblioteca padrão do Python: nada para instalar.
import math
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs
from html import escape

PASTA = os.path.dirname(os.path.abspath(__file__))
PORTA = 8000

GASTOS_EXEMPLO = [
    "Aluguel ou prestação da casa", "Água", "Energia elétrica",
    "Internet e telefone", "Transporte", "Alimentação",
    "Plano de saúde", "Mensalidades", "Parcelas e outras despesas",
]


# ---------- 1. Funções de apoio ----------
def ler_arquivo(nome):
    """Lê um arquivo de texto da pasta do projeto."""
    caminho = os.path.join(PASTA, nome)
    with open(caminho, encoding="utf-8") as arquivo:
        return arquivo.read()


def moeda(valor):
    """Transforma 1234.5 em 'R$ 1.234,50'."""
    sinal = "-" if valor < 0 else ""
    texto = f"{abs(valor):,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sinal}R$ {texto}"


def porcento(valor):
    """Transforma 40.0 em '40,0%'."""
    return f"{valor:.1f}%".replace(".", ",")


def ler_numero(texto, nome, obrigatorio=True):
    """Converte o texto digitado em número. Devolve (numero, erro)."""
    texto = texto.strip().replace("R$", "").replace(" ", "")
    if texto == "":
        if obrigatorio:
            return None, f"Preencha o campo {nome}."
        return 0.0, None
    if "," in texto:                    # formato brasileiro: 1.200,50
        texto = texto.replace(".", "").replace(",", ".")
    elif texto.count(".") == 1 and len(texto.split(".")[1]) == 3:
        texto = texto.replace(".", "")   # 1.200 é mil e duzentos
    try:
        numero = float(texto)
    except ValueError:
        return None, f"O campo {nome} precisa ser um número. Ex.: 1200,50"
    if not math.isfinite(numero):
        return None, f"O campo {nome} precisa ser um número. Ex.: 1200,50"
    if numero < 0:
        return None, f"O campo {nome} não pode ser negativo."
    return numero, None


# ---------- 2. Regras financeiras ----------
def somar_gastos(descricoes, valores):
    """Soma os gastos válidos. Devolve (total, quantidade, sem_valor, erros)."""
    total = 0
    quantidade = 0
    sem_valor = []
    erros = []
    for descricao, texto in zip(descricoes, valores):
        descricao = descricao.strip()
        texto = texto.strip()
        if descricao == "" and texto == "":
            continue                    # linha vazia: ignorada
        if texto == "":
            sem_valor.append(descricao)      # tem nome, mas falta valor
            continue
        if descricao == "":
            erros.append(f"Informe a descrição do gasto de valor {texto}.")
            continue
        valor, erro = ler_numero(texto, f"valor de {descricao}")
        if erro:
            erros.append(erro)
            continue
        total = total + valor
        quantidade = quantidade + 1
    return total, quantidade, sem_valor, erros


def calcular_orcamento(form):
    """Calcula renda, gastos, saldo e percentual. Devolve um dicionário."""
    erros = []
    avisos = []

    salario, erro = ler_numero(form["salario"], "salário líquido")
    if erro:
        erros.append(erro)
    outras, erro = ler_numero(form["outras"], "outras rendas", False)
    if erro:
        erros.append(erro)

    gastos, quantidade, sem_valor, erros_gastos = somar_gastos(
        form["descricoes"], form["valores"])
    erros = erros + erros_gastos
    if sem_valor:
        avisos.append(("alerta", "Gastos sem valor, que não foram somados: "
                    + ", ".join(sem_valor)
                    + ". Digite 0 se não tiver o gasto ou remova a linha."))
    if erros:
        return {"erros": erros, "avisos": avisos}
        
    renda = salario + outras
    if renda == 0:
        return {"erros": ["A renda total precisa ser maior que zero."],
                "avisos": avisos}

    saldo = renda - gastos
    percentual = gastos / renda * 100
    disponivel = max(saldo, 0)    # saldo negativo não é dinheiro disponível

    if saldo < 0:
        avisos.append(("erro", f"Seus gastos superam a renda em "
                    f"{moeda(-saldo)}. Não há dinheiro para distribuir: "
                    "revise os gastos antes de planejar."))
    elif saldo == 0:
        avisos.append(("alerta", "Toda a renda está comprometida com gastos "
                    "fixos. Não sobra valor para distribuir."))
    else:
        avisos.append(("ok", f"Sobram {moeda(saldo)} depois dos gastos "
                    "fixos. Veja abaixo uma sugestão de distribuição."))
    if percentual > 50 and saldo >= 0:
        avisos.append(("info", f"{porcento(percentual)} da renda vai para "
                    "gastos fixos. Veja se algum gasto pode diminuir."))
    if quantidade < 3:
        avisos.append(("info", "Você cadastrou poucos gastos. Confira se não "
                               "esqueceu despesas importantes antes de investir."))
    if form["dividas"]:
        avisos.append(("alerta", "Você marcou que tem dívidas. Priorize "
                    "renegociar e quitar as dívidas antes de investir."))

    return {"erros": [], "avisos": avisos, "renda": renda,
            "gastos": gastos, "saldo": saldo, "percentual": percentual,
            "disponivel": disponivel}


def distribuir(disponivel, form):
    """Divide o valor disponível pelos percentuais. Devolve (partes, erro)."""
    campos = [("pct_reserva", "reserva de emergência"),
              ("pct_invest", "investimentos e metas"),
              ("pct_lazer", "lazer e gastos variáveis")]
    percentuais = []
    for chave, nome in campos:
        pct, erro = ler_numero(form[chave], f"percentual de {nome}")
        if erro:
            return None, erro
        percentuais.append(pct)
        
    soma = sum(percentuais)
    if abs(soma - 100) > 0.001:
        texto = f"{soma:g}".replace(".", ",")
        return None, (f"Os percentuais somam {texto}%. "
                      "Ajuste para que somem exatamente 100%.")

    reserva = round(disponivel * percentuais[0] / 100, 2)
    investimentos = round(disponivel * percentuais[1] / 100, 2)
    lazer = round(disponivel - reserva - investimentos, 2)  # o que sobra
    return [reserva, investimentos, lazer], None


def calcular_meta(form, valor_metas):
    """Calcula quanto guardar por mês para uma meta."""
    if form["meta_valor"].strip() == "" and form["meta_meses"].strip() == "":
        return ("erro", "Preencha o valor e o prazo da meta.")
    valor, erro = ler_numero(form["meta_valor"], "valor da meta")
    if erro:
        return ("erro", erro)
    if valor == 0:
        return ("erro", "O valor da meta precisa ser maior que zero.")
    try:
        meses = int(form["meta_meses"].strip())
    except ValueError:
        return ("erro", "O prazo precisa ser um número inteiro de meses.")
    if meses < 1:
        return ("erro", "O prazo precisa ser de pelo menos 1 mês.")

    mensal = valor / meses
    nome = form["meta_nome"].strip() or "sua meta"
    texto = (f"Para {nome}, guarde cerca de {moeda(mensal)} por mês "
             f"durante {meses} meses para juntar {moeda(valor)}. "
             "Estimativa simples, sem considerar rendimentos.")
    if valor_metas is not None:
        if mensal <= valor_metas:
            texto += (" Cabe na parte de investimentos e metas "
                      f"({moeda(valor_metas)}).")
        else:
            texto += (" É mais do que a parte de investimentos e metas "
                      f"({moeda(valor_metas)}): aumente o prazo.")
    return ("info", texto)


# ---------- 3. Montagem da página ----------
def ler_formulario(dados):
    """Organiza os dados enviados pelo navegador em um dicionário."""
    def campo(nome, padrao=""):
        return dados.get(nome, [padrao])[0]
    descricoes = dados.get("descricao", [])
    valores = dados.get("valor", [])
    while len(valores) < len(descricoes):
        valores.append("")
    return {
        "salario": campo("salario"),
        "outras": campo("outras"),
        "descricoes": descricoes,
        "valores": valores,
        "dividas": campo("dividas") == "sim",
        "pct_reserva": campo("pct_reserva", "50"),
        "pct_invest": campo("pct_invest", "25"),
        "pct_lazer": campo("pct_lazer", "25"),
        "meta_nome": campo("meta_nome"),
        "meta_valor": campo("meta_valor"),
        "meta_meses": campo("meta_meses"),
    }


def montar_gastos(form):
    """Cria uma linha do formulário para cada gasto."""
    linhas = ""
    pares = zip(form["descricoes"], form["valores"])
    for i, (descricao, valor) in enumerate(pares):
        linhas += f"""
          <div class="gasto">
            <input type="text" name="descricao" value="{escape(descricao)}"
                   placeholder="Descrição" aria-label="Descrição {i + 1}">
            <input type="text" name="valor" value="{escape(valor)}"
                   inputmode="decimal" placeholder="0,00"
                   aria-label="Valor {i + 1}">
            <button type="submit" name="acao" value="remover-{i}"
                    formaction="/#gastos" class="botao-remover">Remover</button>
          </div>"""
    return linhas


def montar_mensagens(lista):
    """Transforma a lista de mensagens em parágrafos HTML."""
    html = ""
    for tipo, texto in lista:
        html += f'<p class="mensagem {tipo}">{escape(texto)}</p>\n'
    return html


def montar_pagina(form, acao):
    """Faz os cálculos pedidos e preenche as marcações do index.html."""
    espera = "Aguardando"
    v = {"RENDA": espera, "GASTOS": espera, "SALDO": espera,
         "PERCENTUAL": espera, "DISPONIVEL": espera, "RESERVA": espera,
         "INVEST": espera, "LAZER": espera, "TOTAL_DIST": espera}
    classe_saldo = "neutro"
    avisos = [("info", "Preencha sua renda e seus gastos e clique em "
               "Calcular meu orçamento.")]
    avisos_dist = []
    valor_metas = None
    
    if acao in ("calcular", "meta", "adicionar") or acao.startswith("remover"):
        r = calcular_orcamento(form)
        if r["erros"] and acao == "meta":
            avisos = []          # orçamento incompleto: calcula só a meta
        elif r["erros"]:
            avisos = [("erro", e) for e in r["erros"]] + r["avisos"]
        else:
            avisos = r["avisos"]
            v["RENDA"] = moeda(r["renda"])
            v["GASTOS"] = moeda(r["gastos"])
            v["SALDO"] = moeda(r["saldo"])
            v["PERCENTUAL"] = porcento(r["percentual"])
            v["DISPONIVEL"] = moeda(r["disponivel"])
            if r["saldo"] > 0:
                classe_saldo = "positivo"
            elif r["saldo"] < 0:
                classe_saldo = "negativo"
                
            partes, erro = distribuir(r["disponivel"], form)
            if erro:
                avisos_dist.append(("erro", erro))
            else:
                v["RESERVA"] = moeda(partes[0])
                v["INVEST"] = moeda(partes[1])
                v["LAZER"] = moeda(partes[2])
                v["TOTAL_DIST"] = moeda(sum(partes))
                valor_metas = partes[1]
                if r["disponivel"] == 0:
                    avisos_dist.append(("alerta", "Não há saldo positivo "
                                                  "para distribuir."))
                                                  
    if acao == "adicionar":
        avisos = [("info", "Linha adicionada. Preencha e clique em "
                   "Calcular meu orçamento.")]
    elif acao.startswith("remover"):
        avisos = [("info", "Gasto removido. Clique em Calcular meu "
                   "orçamento para atualizar.")]

    meta = ""
    if acao == "meta":
        meta = montar_mensagens([calcular_meta(form, valor_metas)])
        
    pagina = ler_arquivo("index.html")
    for chave, texto in v.items():
        pagina = pagina.replace("{{" + chave + "}}", texto)
    pagina = pagina.replace("{{CLASSE_SALDO}}", classe_saldo)
    pagina = pagina.replace("{{AVISOS}}", montar_mensagens(avisos))
    pagina = pagina.replace("{{AVISOS_DIST}}", montar_mensagens(avisos_dist))
    pagina = pagina.replace("{{RESULTADO_META}}", meta)
    pagina = pagina.replace("{{LINHAS_GASTOS}}", montar_gastos(form))
    pagina = pagina.replace("{{DIVIDAS}}", "checked" if form["dividas"] else "")
    for chave in ["salario", "outras", "pct_reserva", "pct_invest",
                  "pct_lazer", "meta_nome", "meta_valor", "meta_meses"]:
        marcacao = "{{" + chave.upper() + "}}"
        pagina = pagina.replace(marcacao, escape(form[chave]))
    return pagina


# ---------- 4. Servidor ----------
class Atendente(BaseHTTPRequestHandler):
    """Atende cada pedido (requisição) que chega do navegador."""
    
    def do_GET(self):
        if self.path == "/":
            form = ler_formulario({"descricao": list(GASTOS_EXEMPLO)})
            self.responder(200, "text/html", montar_pagina(form, "inicio"))
        elif self.path == "/style.css":
            self.responder(200, "text/css", ler_arquivo("style.css"))
        else:
            self.responder(404, "text/plain", "Página não encontrada")

    def do_POST(self):
        tamanho = int(self.headers.get("Content-Length", 0))
        corpo = self.rfile.read(tamanho).decode("utf-8")
        dados = parse_qs(corpo, keep_blank_values=True)
        form = ler_formulario(dados)
        acao = dados.get("acao", ["calcular"])[0]
        
        if acao == "adicionar":
            form["descricoes"].append("")
            form["valores"].append("")
        elif acao.startswith("remover-") and acao[8:].isdigit():
            indice = int(acao[8:])
            if indice < len(form["descricoes"]):
                form["descricoes"].pop(indice)
                form["valores"].pop(indice)

        self.responder(200, "text/html", montar_pagina(form, acao))

    def responder(self, codigo, tipo, conteudo):
        dados = conteudo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo + "; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)


if __name__ == "__main__":
    servidor = HTTPServer(("127.0.0.1", PORTA), Atendente)
    print(f"MeuSaldo rodando em http://127.0.0.1:{PORTA}")
    print("Para parar o servidor, aperte Ctrl + C")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")