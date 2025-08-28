-- Apaga as tabelas existentes para garantir um começo limpo.
-- A cláusula "CASCADE" remove objetos dependentes (como chaves estrangeiras).
DROP TABLE IF EXISTS manutencoes CASCADE;
DROP TABLE IF EXISTS historico_movimentacoes CASCADE;
DROP TABLE IF EXISTS aparelhos CASCADE;
DROP TABLE IF EXISTS modelos CASCADE;
DROP TABLE IF EXISTS marcas CASCADE;
DROP TABLE IF EXISTS colaboradores CASCADE;
DROP TABLE IF EXISTS setores CASCADE;
DROP TABLE IF EXISTS status CASCADE;
DROP TABLE IF EXISTS usuarios CASCADE;

-- Tabela de Usuários do Sistema
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    login VARCHAR(50) NOT NULL UNIQUE,
    senha VARCHAR(255) NOT NULL,
    cargo VARCHAR(50) NOT NULL CHECK (cargo IN ('Administrador', 'Editor', 'Leitor'))
);

-- Tabela de Status dos Aparelhos
CREATE TABLE status (
    id SERIAL PRIMARY KEY,
    nome_status VARCHAR(50) NOT NULL UNIQUE
);

-- Tabela de Setores da Empresa
CREATE TABLE setores (
    id SERIAL PRIMARY KEY,
    nome_setor VARCHAR(100) NOT NULL UNIQUE
);

-- Tabela de Colaboradores
CREATE TABLE colaboradores (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE,
    nome_completo VARCHAR(255) NOT NULL,
    cpf VARCHAR(14) UNIQUE,
    gmail VARCHAR(100),
    setor_id INTEGER REFERENCES setores(id),
    data_cadastro DATE NOT NULL
);

-- Tabela de Marcas de Aparelhos
CREATE TABLE marcas (
    id SERIAL PRIMARY KEY,
    nome_marca VARCHAR(100) NOT NULL UNIQUE
);

-- Tabela de Modelos de Aparelhos
CREATE TABLE modelos (
    id SERIAL PRIMARY KEY,
    nome_modelo VARCHAR(100) NOT NULL,
    marca_id INTEGER NOT NULL REFERENCES marcas(id)
);

-- Tabela Principal de Aparelhos (Inventário)
CREATE TABLE aparelhos (
    id SERIAL PRIMARY KEY,
    numero_serie VARCHAR(100) NOT NULL UNIQUE,
    imei1 VARCHAR(15),
    imei2 VARCHAR(15),
    valor NUMERIC(10, 2),
    data_cadastro DATE NOT NULL,
    modelo_id INTEGER NOT NULL REFERENCES modelos(id),
    status_id INTEGER NOT NULL REFERENCES status(id)
);

-- Tabela de Histórico de Movimentações
CREATE TABLE historico_movimentacoes (
    id SERIAL PRIMARY KEY,
    data_movimentacao TIMESTAMP NOT NULL,
    aparelho_id INTEGER NOT NULL REFERENCES aparelhos(id) ON DELETE CASCADE,
    colaborador_id INTEGER REFERENCES colaboradores(id),
    status_id INTEGER NOT NULL REFERENCES status(id),
    localizacao_atual VARCHAR(255),
    observacoes TEXT,
    checklist_devolucao JSONB -- Usando JSONB para melhor performance em PostgreSQL
);

-- Tabela de Manutenções
CREATE TABLE manutencoes (
    id SERIAL PRIMARY KEY,
    aparelho_id INTEGER NOT NULL REFERENCES aparelhos(id) ON DELETE CASCADE,
    colaborador_id_no_envio INTEGER REFERENCES colaboradores(id),
    fornecedor VARCHAR(255),
    data_envio DATE,
    data_retorno DATE,
    defeito_reportado TEXT,
    solucao_aplicada TEXT,
    custo_reparo NUMERIC(10, 2),
    status_manutencao VARCHAR(50) CHECK (status_manutencao IN ('Em Andamento', 'Concluída', 'Sem Reparo'))
);

-- Inserção de Dados Iniciais Essenciais

-- Inserir Status Padrão
INSERT INTO status (nome_status) VALUES
('Em estoque'),
('Em uso'),
('Em manutenção'),
('Baixado/Inutilizado');

-- Inserir um Usuário Administrador Padrão
-- Senha é '123' (hash: a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3)
INSERT INTO usuarios (nome, login, senha, cargo) VALUES
('Administrador Padrão', 'admin', 'a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3', 'Administrador');
