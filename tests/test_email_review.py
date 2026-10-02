"""The broadcast's look: the mail page, the screenshots, and the vision model's critique (browser and model faked)."""

import json

from PIL import Image

from jason.tasks.email_review import CRITIQUE_SCHEMA, critique, critique_lines, mail_page, screenshot


def test_the_mail_page_sets_the_column_width():
    page = mail_page("A & B", "<p>Hi</p>", 390)
    assert ".mail{width:358px" in page and "A &amp; B" in page and "<p>Hi</p>" in page


def test_a_screenshot_is_cropped_to_its_content(tmp_path, monkeypatch):
    monkeypatch.setattr("jason.tasks.email_review.browser", lambda: "chrome")
    page = tmp_path / "x.html"
    page.write_text("<p>x</p>", encoding="utf-8")

    def run(args, **kwargs):
        out = next(a.split("=", 1)[1] for a in args if a.startswith("--screenshot="))
        image = Image.new("RGB", (800, 3000), (255, 255, 255))
        image.paste((0, 0, 0), (10, 10, 300, 500))          # content in the top-left corner
        image.save(out)

    shot = screenshot(page, tmp_path / "x.png", 800, run=run)
    assert Image.open(shot).size == (316, 516)


def test_the_critique_sends_the_images_and_schema(tmp_path):
    images = []
    for name in ("desktop", "phone", "logo"):
        path = tmp_path / f"{name}.png"
        Image.new("RGB", (4, 4)).save(path)
        images.append(path)
    sent = {}
    answer = {"summary": "Clear.", "strengths": ["short"],
              "suggestions": [{"area": "readability", "issue": "long", "change": "split", "priority": "low"},
                              {"area": "hierarchy", "issue": "flat", "change": "use headings", "priority": "high"}]}

    def post(url, payload):
        sent.update(payload)
        return {"message": {"content": json.dumps(answer)}}

    data = critique(images, has_logo=True, post=post)
    message = sent["messages"][0]
    assert len(message["images"]) == 3 and "letterhead logo" in message["content"]
    assert sent["format"] == CRITIQUE_SCHEMA and sent["think"] is False
    lines = critique_lines(data)
    table = [line for line in lines if line.startswith("| high") or line.startswith("| low")]
    assert table[0].startswith("| high")                                # highest priority first


SENT = """<html><body><table><tr><td><img src="https://core.payhoa.com/org-logo/27889?v=1&signature=x" alt="PayHOA.com"></td></tr>
<tr><td width="20"></td><td width="520"><table><tr>
                                <td valign="middle" align="left"

                                    style="line-height: 1.4;"><p>Hi Pat,</p><p>The meeting.</p></td>

                            </tr>

                        </table>

                    </td>

                    <td width="20" style="border-right: 1px solid #EDECED"></td></tr></table>
<img src="https://url7216.payhoa.com/wf/open?upn=abc" alt="" width="1" height="1" border="0"></body></html>"""


def test_the_payhoa_layout_is_kept_without_the_message_or_the_tracking_pixel():
    import pytest

    from jason.tasks.email_review import BODY_SLOT, payhoa_wrapper, wrapped_page

    wrapper = payhoa_wrapper(SENT)
    assert BODY_SLOT in wrapper and "Hi Pat" not in wrapper and "/wf/open" not in wrapper and "org-logo/27889" in wrapper
    page = wrapped_page(wrapper, "Subject & more", "<p>Body</p>")
    assert "<p>Body</p>" in page and "Subject &amp; more" in page
    with pytest.raises(ValueError):
        payhoa_wrapper("<html><body><p>not PayHOA</p></body></html>")
