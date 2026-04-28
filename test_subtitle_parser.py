from youtube_subtitle_encoder import (
    clean_caption_text,
    milliseconds_to_timestamp,
    parse_json3,
    parse_vtt,
    safe_filename,
)


def test_parse_vtt_removes_tags_and_dedupes_text():
    content = """WEBVTT

00:00:01.000 --> 00:00:03.000
<c>Hello&nbsp;world</c>

00:00:03.000 --> 00:00:05.000
<c>Hello&nbsp;world</c>

00:00:05.000 --> 00:00:06.000
Next line
"""

    captions = parse_vtt(content)

    assert [caption.text for caption in captions] == ["Hello world", "Next line"]
    assert captions[0].start == "00:00:01.000"


def test_parse_json3():
    content = """
    {
      "events": [
        {"tStartMs": 1200, "dDurationMs": 800, "segs": [{"utf8": "Hi "}, {"utf8": "there"}]},
        {"tStartMs": 2000, "dDurationMs": 1000, "segs": [{"utf8": "\\n"}]}
      ]
    }
    """

    captions = parse_json3(content)

    assert len(captions) == 1
    assert captions[0].start == "00:00:01.200"
    assert captions[0].end == "00:00:02.000"
    assert captions[0].text == "Hi there"


def test_helpers():
    assert clean_caption_text("<b>A&nbsp; B</b>") == "A B"
    assert milliseconds_to_timestamp(3_661_007) == "01:01:01.007"
    assert safe_filename("bad/name: ok?") == "badname ok"
