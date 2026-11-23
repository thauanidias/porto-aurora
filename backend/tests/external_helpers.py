from consent_helpers import consent_signature


def complete_data():
    return {"desired_position": "Analista de Teste", "personal": {"name": "Pessoa de Teste", "birth_date": "1990-01-02", "email": "pessoa@example.com", "mobile": "91999991234", "address": {"street": "Rua Exemplo", "city": "Barcarena", "state": "PA"}},
            "documents": {"cpf": "00000000000", "rg": "RG-TESTE"},
            "bank": {"bank_name": "Banco de Teste", "branch": "1234", "checking_account": "9876"},
            "dependents": [{"name": "Dependente de Teste", "mother_name": "Mae de Teste", "mother_cpf": "00000000000", "cpf": "00000000000"}],
            "employment": {"company": "Empresa de Teste", "description": "Atividade completa de teste. " * 150},
            "declaration": {"accepted": True, "place": "Barcarena", "date": "2026-10-28", "signature_name": "Pessoa de Teste", "signature_image": consent_signature()}}

