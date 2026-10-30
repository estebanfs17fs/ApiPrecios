from click.testing import CliRunner

from precios_uy.cli import cli


class TestCliListar:
    def test_listar_sin_datos(self, runner: CliRunner):
        result = runner.invoke(cli, ["listar"])
        assert result.exit_code == 0
        assert "No hay productos registrados" in result.output

    def test_listar_con_datos(self, runner: CliRunner, productos_db):
        result = runner.invoke(cli, ["listar"])
        assert result.exit_code == 0
        for p in productos_db:
            assert p.nombre[:60] in result.output

    def test_listar_con_filtro(self, runner: CliRunner, productos_db):
        result = runner.invoke(cli, ["listar", "--supermercado", "Disco"])
        assert result.exit_code == 0
        assert "Arroz" in result.output

    def test_listar_con_limite(self, runner: CliRunner, productos_db):
        result = runner.invoke(cli, ["listar", "--limite", "2"])
        assert result.exit_code == 0
        lines = [line for line in result.output.split("\n") if "]" in line]
        assert len(lines) <= 2


class TestCliBuscar:
    def test_buscar_sin_resultados(self, runner: CliRunner):
        result = runner.invoke(cli, ["buscar", "xyznoexiste"])
        assert result.exit_code == 0
        assert "no se encontraron" in result.output.lower()

    def test_buscar_con_resultados(self, runner: CliRunner, productos_db):
        result = runner.invoke(cli, ["buscar", "Arroz"])
        assert result.exit_code == 0
        assert "Arroz" in result.output
        assert "$" in result.output

    def test_buscar_case_insensitive(self, runner: CliRunner, productos_db):
        result = runner.invoke(cli, ["buscar", "arroz"])
        assert result.exit_code == 0
        assert "Arroz" in result.output


class TestCliSupermercados:
    def test_sin_datos(self, runner: CliRunner):
        result = runner.invoke(cli, ["supermercados"])
        assert result.exit_code == 0
        assert "No hay datos" in result.output

    def test_con_datos(self, runner: CliRunner, productos_db):
        result = runner.invoke(cli, ["supermercados"])
        assert result.exit_code == 0
        assert "Disco" in result.output
        assert "Tienda Inglesa" in result.output
