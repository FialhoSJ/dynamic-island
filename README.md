# Ilha Dinâmica para Windows

A ilha mostra música do Spotify, YouTube e outros aplicativos que publicam informações de mídia no Windows. Quando um programa reproduz som sem fornecer título e capa, a ilha detecta a saída de áudio e mostra o aplicativo (ou a saída, se o Windows não informar a origem).

## Executar

No PowerShell, dentro desta pasta:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe dynamic-island.py
```

Clique na cápsula para abrir o painel. O menu da bandeja permite mostrar, ocultar ou encerrar a ilha.

Os controles, a capa e o nome da faixa dependem das informações que o aplicativo publica nas sessões de mídia do Windows. A detecção genérica de áudio cobre as saídas ativas, mas não consegue identificar a faixa nem controlar um aplicativo que não fornece esses dados.
