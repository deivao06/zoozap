# Capivara v1 — Design

Data: 2026-09-28

## Objetivo

Uma capivara que vive na borda da tela e **entrega mensagens**. Mensagens chegam de scripts (`curl`), webhooks de serviços da rede local e outras pessoas na mesma rede. Referência: Desktop Goose, mas **sem ser chata**.

Plataformas do cliente: **Windows e Linux**.

## Escopo

**Na v1:**
- Servidor em Docker que recebe, guarda e repassa mensagens.
- Cliente nativo com a capivara "drawer", pilha de bilhetes e histórico.
- Várias capivaras conectadas; quem envia escolhe uma ou mais.

**Fora da v1:**
- Autenticação (servidor só na rede local).
- Serviços na nuvem enviando direto (não alcançam a rede local).
- Enviar mensagem de dentro do cliente (v2).
- Customização da capivara (chapéu, óculos) e a capivara do remetente aparecer no destino (v3).
- Link e prioridade nas mensagens.
- Arrastar a capivara.

## Arquitetura

```
 curl / webhook / script
          │  POST /notify
          ▼
 ┌─────────────────────┐
 │ servidor (Docker)   │  FastAPI + SQLite
 └─────────────────────┘
          │  WebSocket /ws
    ┌─────┴──────┐
    ▼            ▼
 capivara     capivara      (PySide6, nativo)
```

- **Servidor:** FastAPI + SQLite, sobe com `docker compose up -d`. O arquivo do SQLite fica num volume.
- **Cliente:** PySide6, roda fora do Docker. No Linux, usa XWayland (`QT_QPA_PLATFORM=xcb`).
- Sem engine de jogo.

## Identificação das capivaras

- Na primeira execução, o cliente **gera um UUID** e salva num arquivo local. Ele nunca muda.
- O cliente também tem um **apelido** (`name`), configurável. **Apelidos podem repetir.**
- IP **não** é usado para identificar.

## Regras de entrega

- Um item de `to` casa com uma capivara se for igual ao **ID** ou ao **apelido** dela.
- Apelido casa com **todas** as capivaras que têm esse apelido.
- **Sem `to`** → vai para **todas** as capivaras que **já conectaram alguma vez**.
- Itens de `to` que **não casam com nenhuma** capivara conhecida são **ignorados** e devolvidos em `unknown` na resposta.
- Capivara **offline** → a mensagem espera no servidor e é entregue quando ela conectar.
- A leitura é **por capivara**: ler numa não afeta as outras.
- Uma capivara nova **não recebe** mensagens enviadas antes de ela conectar pela primeira vez.

## API

### `POST /notify`

```json
{"text": "build terminou", "title": "Build", "sender": "CI", "to": ["david", "7f3a..."]}
```

- `text`: obrigatório, 1 a 2000 caracteres.
- `title`, `sender`: opcionais, texto.
- `to`: opcional, lista de IDs ou apelidos.
- `sender_look`: opcional, **reservado** para a v3. Aceito e ignorado.
- Resposta `201`: `{"id": 42, "unknown": []}`.
- `text` ausente, vazio ou maior que 2000 → `422`.

### `GET /clients`

```json
[{"id": "7f3a...", "name": "david", "online": true}]
```

### `GET /history?id=<uuid>`

Últimas **50** mensagens **lidas** por essa capivara, da mais nova para a mais antiga.

### WebSocket `/ws?id=<uuid>&name=<apelido>`

- Ao conectar: o servidor registra/atualiza a capivara (apelido, visto por último) e envia **todas as mensagens pendentes** dela.
- Servidor → cliente: `{"type": "message", "id": 42, "sender": "CI", "title": "Build", "text": "build terminou"}`
- Cliente → servidor: `{"type": "read", "id": 42}` → marca a entrega como lida.
- Duas conexões com o **mesmo ID**: a nova substitui a antiga.

## Banco (SQLite)

- `messages`: `id`, `sender`, `title`, `text`, `created_at`
- `clients`: `id` (UUID), `name`, `last_seen`
- `deliveries`: `message_id`, `client_id`, `read_at` (nulo = pendente)

## Cliente

### Janela

- Sem borda, fundo transparente, sempre por cima, fora da barra de tarefas.
- Posicionada dentro da **área livre da tela** (acima da barra de tarefas).

### Área de hover

- Faixa pequena (cerca de 8px × 120px) no canto da borda configurada. Não ocupa a borda inteira.

### Estados

```
escondida ──hover──▶ espiando (só a cabeça, saindo da água) ──mouse sai──▶ escondida
    │
 chega mensagem
    ▼
 entrando (andando) ─▶ esperando [N] ─clique─▶ lendo
                           ▲                    │ fecha → envia "read"
                           └──── ainda tem ─────┤
                                                ▼ acabou
                                     saindo (andando) ─▶ escondida
```

- Mensagem que chega durante `entrando`, `esperando` ou `lendo` entra na pilha.
- Mensagem que chega durante `espiando` ou `saindo` faz ela voltar para `entrando`.
- O contador `[N]` mostra quantos bilhetes ainda não foram lidos.

### Interações

- **Clique** na capivara em `esperando` → abre o bilhete (remetente, título, texto).
- **Botão direito** (em `espiando` ou `esperando`) → menu: **Histórico**, **Sair**. Quando desconectado, o menu mostra **"desconectado"**.
- **Histórico** abre uma janela com as últimas 50 lidas (`GET /history`).

### Configuração

Arquivo `config.toml` na pasta de configuração do usuário:

```toml
server = "http://192.168.0.10:8000"
name = "david"
edge = "bottom"   # bottom | left | right
```

O UUID fica num arquivo separado na mesma pasta, criado automaticamente.

### Arte

Sprites simples e provisórios. A arte final entra depois, trocando só os arquivos.

## Erros

- **Servidor fora do ar:** o cliente reconecta sozinho com espera crescente (1s, 2s, 4s… até 30s). A capivara fica escondida.
- **Confirmação de leitura perdida:** a mensagem volta ao reconectar; o cliente ignora IDs que já estão na pilha ou já foram lidos nesta sessão.
- **Mensagem inválida no WebSocket:** o servidor ignora.

## Testes

- **Servidor:** `pytest` + `TestClient` do FastAPI (HTTP e WebSocket), SQLite temporário, feito com TDD.
- **Cliente:** máquina de estados numa classe **sem Qt**, testada com `pytest`. Leitura do `config.toml` e criação do UUID também testadas.
- **Parte visual:** verificada rodando de verdade no Linux. No Windows, verificação manual.
