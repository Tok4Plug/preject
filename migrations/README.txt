# Migrações do Banco de Dados

Este diretório contém migrações do banco de dados usando Alembic.

## Estrutura

- `versions/` - Arquivos de migração individuais
- `env.py` - Configuração do ambiente Alembic
- `script.py.mako` - Template para novos arquivos de migração

## Comandos Úteis

### Criar nova migração
```bash
alembic revision --autogenerate -m "descricao_da_migracao"