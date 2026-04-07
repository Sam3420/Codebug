from server.patch_engine import apply_patch


def test_apply_json_patch():
    source = "a = 1\nb = 2\n"
    patched, changed = apply_patch(source, '[{"line_no": 2, "content": "b = 3"}]')
    assert patched == "a = 1\nb = 3\n"
    assert changed == 1


def test_apply_full_source_patch():
    source = "a = 1\n"
    patched, changed = apply_patch(source, "a = 2\n")
    assert patched == "a = 2\n"
    assert changed == 1
