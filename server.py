#!/usr/bin/env python3
"""
Servidor mínimo para servir a aplicação de Parâmetros Sindicais.

Uso:
    python3 server.py [porta]

Porta padrão: 8000

Acesse em: http://localhost:8000
"""

import http.server
import os
import sys


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

    # Serve from repository root so data/ and app files are accessible
    repo_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(repo_root)

    handler = http.server.SimpleHTTPRequestHandler

    with http.server.HTTPServer(("", port), handler) as httpd:
        print(f"Parâmetros Sindicais disponível em: http://localhost:{port}")
        print("Pressione Ctrl+C para encerrar.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor encerrado.")


if __name__ == "__main__":
    main()
