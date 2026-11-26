"""Inicialização local para o atalho do Windows."""

import threading
import webbrowser


def main():
    try:
        from werkzeug.serving import make_server
        from ponto_apoio import create_app
    except ImportError:
        print("Dependências não encontradas. Consulte a primeira instalação no README.")
        return 1

    try:
        server = make_server("127.0.0.1", 5000, create_app())
    except OSError:
        print("A porta 5000 já está em uso. Verifique se o sistema já está aberto ou se outro programa usa essa porta.")
        return 1
    except SystemExit:
        # Werkzeug pode encerrar a inicialização quando a porta está ocupada.
        print("Não foi possível reservar a porta 5000. Verifique se o sistema já está aberto.")
        return 1

    address = "http://127.0.0.1:5000"
    print(f"Ponto de Apoio iniciado em {address}")
    print("Mantenha esta janela aberta. Para encerrar, pressione Ctrl+C.")
    threading.Thread(target=webbrowser.open, args=(address,), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSistema encerrado.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
