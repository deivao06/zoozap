# zoozap

Uma capivara em pixel art que mora na borda da sua tela e entrega mensagens.

Uma pessoa sobe o **servidor**. As outras instalam o **cliente** e entram com um **convite**.

## 1. Subir o servidor

Precisa de Docker. Na pasta do projeto, rode:

```
docker compose up -d
```

O servidor fica na porta **8000**. Na primeira vez ele gera uma **chave secreta**, que continua a mesma enquanto o volume do Docker existir.

## 2. Montar o convite

O formato do convite é:

```
zoo://IP_DA_MAQUINA:8000#CHAVE
```

**IP da máquina** que roda o servidor:

```
ip -4 route get 1.1.1.1 | grep -oP 'src \K\S+'
```

No Windows, use o `ipconfig` e pegue o "Endereço IPv4".

**Chave**, que aparece no log do servidor:

```
docker compose logs server | grep chave
```

A linha tem este formato: `zoozap: chave AbC123xyz`

**Juntando as duas partes**, fica assim:

```
zoo://192.168.0.10:8000#AbC123xyz
```

Mande esse texto pra quem vai usar o cliente.

> Quem tiver o convite consegue mandar mensagem pra todas as capivaras, então mande só pra quem você confia.

## 3. Instalar o cliente

Baixe o arquivo do seu sistema na página de [Releases](https://github.com/deivao06/zoozap/releases/latest):

- **Windows:** `zoozap-windows.exe`. Se aparecer o aviso do SmartScreen, clique em **Mais informações** e depois em **Executar assim mesmo**.
- **Linux:** `zoozap-linux`. Antes de abrir, dê permissão de execução:
  ```
  chmod +x zoozap-linux
  ./zoozap-linux
  ```

Quando sair uma versão nova, a capivara avisa e se atualiza sozinha.

## 4. Colar o convite

1. Copie o convite.
2. Passe o mouse na borda da tela até a capivara espiar e clique nela.
3. Abra **CONFIG** e clique em **COLAR CONVITE**.

A bolinha ao lado do nome, no menu, fica verde quando a capivara está conectada.

## Mandar mensagem por script

```
curl -X POST http://IP:8000/notify \
  -H "Authorization: Bearer CHAVE" \
  -H "Content-Type: application/json" \
  -d '{"text": "deploy terminou", "title": "CI", "sender": "github"}'
```

Sem o campo `"to"`, a mensagem vai pra todas as capivaras. Pra escolher quem recebe, use `"to": ["nome"]`.

## Problemas comuns

- **A capivara não conecta:** confira se a porta 8000 está liberada no firewall da máquina do servidor e se o IP do convite continua o mesmo, porque o roteador pode trocar o IP.
- **Linux com compositor (picom etc.):** a capivara aparece com sombra ou com fundo borrado. Exclua a janela de classe `zoozap` das regras de blur e de sombra, por exemplo com `"class_g = 'zoozap'"`.
