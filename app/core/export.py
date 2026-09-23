import markdown
from xhtml2pdf import pisa

REPORT_CSS = """
body { font-family: Helvetica, sans-serif; margin: 2em; line-height: 1.5; }
h1 { color: #1a1a1a; border-bottom: 2px solid #444; }
h2 { color: #333; margin-top: 1.5em; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; }
th, td { border: 1px solid #ccc; padding: 0.4em 0.8em; text-align: left; }
th { background-color: #f0f0f0; }
"""


class PdfRenderError(RuntimeError):
    """xhtml2pdf a signalé une erreur pendant le rendu."""


def markdown_to_html(report_md: str) -> str:
    """Convertit le Markdown du rapport en HTML autonome, tableaux inclus."""
    body = markdown.markdown(report_md, extensions=["tables"])
    return f"<html><head><style>{REPORT_CSS}</style></head><body>{body}</body></html>"


def render_report_pdf(report_md: str, output_path: str) -> None:
    """Génère le PDF du rapport à l'emplacement demandé."""
    html = markdown_to_html(report_md)
    with open(output_path, "wb") as output_file:
        result = pisa.CreatePDF(html, dest=output_file)

    if result.err:
        raise PdfRenderError(f"Échec du rendu PDF ({result.err} erreur(s)).")
