import io
import logging

from attrpipe.core.logging import configure_logging, get_logger


class TestLogging:
    def test_configure_and_log_cyrillic_does_not_raise(self) -> None:
        # Regression: logging non-ASCII must not crash on a legacy console encoding.
        configure_logging("attrpipe-test")
        logger = get_logger("test")
        logger.info("attribute_unmapped", raw_attribute="Загальна маса виробу")

    def test_configure_forces_utf8_on_reconfigurable_stream(self) -> None:
        stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
        assert stream.encoding.lower() == "cp1252"
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        stream.write("Вага 2.3 кг")  # would raise under cp1252
        assert stream.encoding.lower() == "utf-8"

    def teardown_method(self) -> None:
        logging.getLogger().handlers.clear()
