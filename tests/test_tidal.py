import base64

from streamrip.client.downloadable import TidalMpdDownloadable
from streamrip.client.tidal import (
    TidalClient,
    _format_segment_template,
    _parse_dash_manifest,
)
from streamrip.config import Config
from util import arun

EXAMPLE_DASH_MANIFEST = b"""<?xml version='1.0' encoding='UTF-8'?>
<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="static" mediaPresentationDuration="PT4M0.0S" minBufferTime="PT2S" profiles="urn:mpeg:dash:profile:isoff-on-demand:2011">
  <Period id="0">
    <AdaptationSet id="0" contentType="audio" mimeType="audio/mp4" segmentAlignment="true">
      <Representation id="FLAC_HIRES,96000,24" codecs="flac" bandwidth="2773973" audioSamplingRate="96000">
        <SegmentTemplate timescale="96000"
          initialization="https://sp-ad-fa.audio.tidal.com/mediatracks/abc/0.mp4?token=xyz"
          media="https://sp-ad-fa.audio.tidal.com/mediatracks/abc/$Number$.mp4?token=xyz"
          startNumber="1">
          <SegmentTimeline>
            <S d="380928" r="69"/>
            <S d="128210"/>
          </SegmentTimeline>
        </SegmentTemplate>
      </Representation>
    </AdaptationSet>
  </Period>
</MPD>"""


def test_format_segment_template():
    assert _format_segment_template("seg-$Number$.mp4", 5) == "seg-5.mp4"
    assert _format_segment_template("seg-$Number%05d$.mp4", 5) == "seg-00005.mp4"
    assert _format_segment_template("seg.mp4", 5) == "seg.mp4"


def test_parse_dash_manifest():
    urls, codec = _parse_dash_manifest(EXAMPLE_DASH_MANIFEST)
    assert codec == "flac"
    # init segment + 70 repeats (r=69 -> 70 occurrences) + 1 final segment
    assert len(urls) == 1 + 71
    assert urls[0] == "https://sp-ad-fa.audio.tidal.com/mediatracks/abc/0.mp4?token=xyz"
    assert urls[1] == "https://sp-ad-fa.audio.tidal.com/mediatracks/abc/1.mp4?token=xyz"
    assert urls[-1] == "https://sp-ad-fa.audio.tidal.com/mediatracks/abc/71.mp4?token=xyz"


def test_get_downloadable_dispatches_dash_manifest(monkeypatch):
    config = Config.defaults()
    client = TidalClient(config)

    manifest_b64 = base64.b64encode(EXAMPLE_DASH_MANIFEST).decode()

    async def fake_api_request(path, params=None, base=None):
        return {
            "manifest": manifest_b64,
            "manifestMimeType": "application/dash+xml",
            "audioQuality": "HI_RES_LOSSLESS",
        }

    monkeypatch.setattr(client, "_api_request", fake_api_request)

    downloadable = arun(client.get_downloadable("12345", 3))
    assert isinstance(downloadable, TidalMpdDownloadable)
    assert downloadable.extension == "flac"
    assert len(downloadable.segment_urls) == 72


def test_get_downloadable_still_handles_bts_manifest(monkeypatch):
    import json

    config = Config.defaults()
    client = TidalClient(config)

    bts_manifest = {
        "mimeType": "audio/flac",
        "codecs": "flac",
        "encryptionType": "NONE",
        "urls": ["https://example.com/track.flac"],
    }
    manifest_b64 = base64.b64encode(json.dumps(bts_manifest).encode()).decode()

    async def fake_api_request(path, params=None, base=None):
        return {
            "manifest": manifest_b64,
            "manifestMimeType": "application/vnd.tidal.bts",
            "audioQuality": "LOSSLESS",
        }

    monkeypatch.setattr(client, "_api_request", fake_api_request)

    downloadable = arun(client.get_downloadable("12345", 2))
    assert downloadable.url == "https://example.com/track.flac"
    assert downloadable.extension == "flac"
