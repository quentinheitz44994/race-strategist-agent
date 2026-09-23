from app.core.export import markdown_to_html, render_report_pdf


def test_markdown_to_html_convertit_titres_et_tableaux():
    report_md = "# Titre\n\n| Segment | Pente |\n|---|---|\n| 0 | 8% |\n"
    html = markdown_to_html(report_md)

    assert "<h1>Titre</h1>" in html
    assert "<table>" in html
    assert "<td>8%</td>" in html


def test_render_report_pdf_produit_un_fichier_pdf_valide(tmp_path):
    output = tmp_path / "rapport.pdf"
    render_report_pdf("# Rapport\n\nContenu de test.", str(output))

    assert output.exists()
    assert output.read_bytes().startswith(b"%PDF")
