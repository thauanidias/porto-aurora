import io
import zipfile
from uuid import uuid4

from sqlalchemy import select

from app.models import ConsentReceipt
from app.services.electronic_acceptance import acceptance_signature


def test_click_acceptance_unlocks_candidate_without_rh_release_and_records_proof(client, db):
    email = 'click-' + uuid4().hex[:8] + '@example.com'
    signup = client.post('/api/v1/auth/register', json={'name':'Pessoa do Aceite','email':email,'consent':False,'defer_consent_to_profile':True})
    assert signup.status_code == 201
    token = signup.json()['test_setup_url'].split('#token=',1)[1].split('&',1)[0]
    login = client.post('/api/v1/auth/consume-link',json={'token':token,'password':'Ca42!?'})
    headers = {'Authorization':'Bearer '+login.json()['access_token']}
    denied = client.put('/api/v1/candidates/me/sensitive',headers=headers,json={'data':{},'purpose':'Teste de aceite','consent':True})
    assert denied.status_code == 403 and denied.json()['code'] == 'CONSENT_REQUIRED'
    body={'name':'Nome ignorado','email':'ignored@example.com','context':'CADASTRO','accepted':True}
    assert client.post('/api/v1/public/consent-receipts',headers=headers,json=body).status_code == 422
    accepted = client.post('/api/v1/public/consent-receipts',headers=headers,json={**body,'read_to_end':True})
    assert accepted.status_code == 201, accepted.text
    result=accepted.json()
    assert result['signature_method']=='CLICK_ACCEPTANCE'
    assert result['name']=='Pessoa do Aceite' and result['email']==email
    row=db.scalar(select(ConsentReceipt).where(ConsentReceipt.id==result['id']))
    assert not row.document_snapshot['signature_image']
    record=row.document_snapshot['acceptance_record']
    assert record['accepted'] and record['read_to_end']
    assert acceptance_signature(record)==row.document_snapshot['electronic_signature_sha256']
    proof=client.get(result['download_url'])
    assert proof.status_code==200
    with zipfile.ZipFile(io.BytesIO(proof.content)) as archive:
        xml=archive.read('word/document.xml').decode()
        assert result['electronic_signature_sha256'] in xml
        assert 'word/media/consent-signature.png' not in archive.namelist()
    journey=client.get('/api/v1/candidates/me/journey',headers=headers).json()
    assert journey['sections']['consent']['enabled'] is True
    allowed=client.put('/api/v1/candidates/me/sensitive',headers=headers,json={'data':{},'purpose':'Teste de aceite','consent':True})
    assert allowed.status_code==200,allowed.text
