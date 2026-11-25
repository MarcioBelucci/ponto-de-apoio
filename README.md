# Central de Outreaches MLP

Aplicação local para organizar alunos, criar outreaches e abrir mensagens personalizadas no WhatsApp Desktop.

## Como iniciar

1. Instale o Python 3.11 ou mais recente, caso necessário.
2. Abra o PowerShell nesta pasta.
3. Execute:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

4. Abra `http://127.0.0.1:5000` no navegador.

Os dados ficam no arquivo `data\outreaches.db`. Para parar o sistema, pressione `Ctrl+C` no PowerShell.

## Backup e restauração

Na página **Backup**, baixe periodicamente uma cópia e guarde-a em local seguro, preferencialmente fora deste computador. O backup contém dados pessoais e histórico de contatos.

Para restaurar, pare o sistema com `Ctrl+C`. Na pasta `data`, renomeie `outreaches.db` para preservar a versão atual. Copie o arquivo de backup para essa pasta e renomeie a cópia para `outreaches.db`. Inicie o sistema novamente e confira os dados. A restauração volta os dados ao momento da criação do backup; alterações posteriores não estarão nele. Não substitua o arquivo com o sistema aberto.

## Como usar

- Importe uma planilha `.xlsx` ou `.csv` com os nomes dos alunos. Na importação, informe qual coluna contém os nomes.
- Preencha o telefone de cada aluno uma única vez na tela **Alunos**.
- Crie um outreach e use `{nome}` onde a mensagem deve incluir o primeiro nome do aluno.
- Em um outreach, use **Abrir no WhatsApp** para abrir a conversa no aplicativo WhatsApp Desktop instalado no Windows. A alternativa Web permanece disponível no menu **Mais**. Confirme o envio no próprio WhatsApp e então marque o aluno como enviado no sistema.
- Enquanto o outreach estiver **Em andamento**, alunos adicionados posteriormente serão incluídos nele automaticamente. Ao fim da semana, clique em **Encerrar outreach** para preservar sua lista de destinatários.

O sistema nunca envia mensagens sozinho.

Por padrão, a chave de sessão é gerada ao iniciar o sistema. Ao reiniciar, atualize as páginas abertas antes de enviar formulários. Para manter a sessão entre reinícios, configure a variável de ambiente `OUTREACHES_SECRET` com uma chave longa e aleatória, mantida em segredo.

## Testes

Com o ambiente virtual ativado e as dependências instaladas, execute antes de cada alteração:

```powershell
python -m unittest discover -s tests -v
```

Os testes usam um banco SQLite em memória e não alteram os dados locais.
