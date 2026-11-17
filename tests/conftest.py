import pytest

from exam_uncheat.signatures import SignatureDB


@pytest.fixture(scope="session")
def sigdb():
    return SignatureDB.load()
