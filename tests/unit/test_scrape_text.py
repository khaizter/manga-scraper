"""Unit tests for manga detail text cleanup helpers."""

from app.services.scrape_manga_details import strip_label_value, strip_summary_heading


class TestStripLabelValue:
    def test_should_extract_value_after_colon(self) -> None:
        """Should return the text after the first colon."""
        assert strip_label_value("Author : Yuki Tabata") == "Yuki Tabata"

    def test_should_return_trimmed_text_when_no_colon_is_present(self) -> None:
        """Should return the original text when there is no label prefix."""
        assert strip_label_value("Ongoing") == "Ongoing"


class TestStripSummaryHeading:
    def test_should_remove_summary_heading_line(self) -> None:
        """Should strip the plot summary heading and keep the body text."""
        text = "Plot Summary:\n\nAsta dreams of becoming Wizard King."
        assert strip_summary_heading(text) == "Asta dreams of becoming Wizard King."
