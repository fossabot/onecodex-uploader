from sniff import sniff_file
from upload import check_version, get_apikey
from version import __version__

SERVER = 'https://app.onecodex.com/'

# TODO: some PyQt tests for the GUI


def test_sniffer():
    resp = sniff_file('onecodex_uploader/test_data/test.fa')

    assert resp['compression'] == 'none'
    assert resp['file_type'] == 'fasta'
    assert resp['seq_type'] == 'dna'

    assert not resp['seq_multiline']
    assert not resp['seq_has_gaps']
    assert not resp['seq_has_lowercase']
    assert not resp['seq_has_iupac']
    assert not resp['seq_has_unknowns']

    assert resp['seq_est_avg_len'] == 74.
    assert resp['seq_est_gc'] == 0.5

    assert not resp['interleaved']


def test_check_version():
    should_upgrade, msg = check_version(__version__, SERVER, 'gui')

    assert not should_upgrade
    assert msg is None or msg.startswith('Please upgrade your client to the latest version')


def test_login():
    resp = get_apikey('test', 'test', SERVER)
    assert resp is None  # should not be able to log in with this
