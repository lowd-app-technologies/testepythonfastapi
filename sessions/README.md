# Diretório de Sessões do Instagram

Este diretório armazena os cookies e informações de sessão do Instagram para permitir login automático sem necessidade de autenticação repetida.

## Funcionamento

- Após um login bem-sucedido, a sessão (cookies) é salva nesta pasta
- Nas próximas execuções, o sistema tenta usar a sessão salva antes de solicitar nova autenticação
- As sessões expiram após 48 horas para garantir segurança

## Arquivos

Para cada usuário, são criados dois arquivos:
- `<username>_cookies.pkl` - Contém os cookies da sessão do navegador
- `<username>_metadata.json` - Contém metadados como horário do último login

## Como usar

Para usar uma sessão salva, simplesmente forneça o parâmetro `use_saved_session: true` na solicitação JSON:

```json
{
  "username": "seu_usuario",
  "password": "sua_senha",
  "use_saved_session": true
}
```

Para forçar uma nova autenticação, defina `use_saved_session: false`.

## Segurança

- Os cookies são armazenados apenas localmente
- As senhas nunca são armazenadas
- Recomenda-se manter este diretório protegido com permissões restritas
