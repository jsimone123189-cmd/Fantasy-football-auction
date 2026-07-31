from draft_helper.parsing import iter_collection, merge_fragments


def test_iter_collection_indexed_dict():
    obj = {"0": "a", "1": "b", "count": 2}
    assert list(iter_collection(obj)) == ["a", "b"]


def test_iter_collection_respects_count_over_extra_keys():
    obj = {"0": "a", "1": "b", "2": "should be ignored", "count": 2}
    assert list(iter_collection(obj)) == ["a", "b"]


def test_iter_collection_plain_list():
    assert list(iter_collection(["a", "b"])) == ["a", "b"]


def test_iter_collection_none():
    assert list(iter_collection(None)) == []


def test_merge_fragments_flat_list():
    frags = [{"a": 1}, {"b": 2}, {"c": 3}]
    assert merge_fragments(frags) == {"a": 1, "b": 2, "c": 3}


def test_merge_fragments_nested_list():
    frags = [[{"a": 1}, {"b": 2}]]
    assert merge_fragments(frags) == {"a": 1, "b": 2}


def test_merge_fragments_preserves_nested_collections():
    frags = [{"a": 1}, {"games": {"0": {"x": 1}, "count": 1}}]
    merged = merge_fragments(frags)
    assert merged["a"] == 1
    assert merged["games"] == {"0": {"x": 1}, "count": 1}
