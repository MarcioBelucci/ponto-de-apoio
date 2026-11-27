# Central de Outreaches MLP

Aplicação local para organizar alunos, criar outreaches e abrir mensagens personalizadas no WhatsApp Desktop.

## Primeira instalação

1. Instale o Python 3.11 ou mais recente, caso necessário.
2. Abra o PowerShell nesta pasta.
3. Execute:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

4. Feche o PowerShell.

## Como iniciar

Dê duplo clique em **Iniciar Ponto de Apoio.bat**. O navegador abrirá automaticamente; se não abrir, acesse `http://127.0.0.1:5000` manualmente. Mantenha a janela do sistema aberta enquanto o utiliza. Para encerrar, pressione `Ctrl+C` nessa janela ou feche-a.

Se aparecer uma mensagem sobre ambiente ou dependências ausentes, siga a primeira instalação acima. Se a porta 5000 estiver ocupada, verifique se o sistema já está aberto ou se outro programa está usando essa porta. Você pode criar um atalho para o arquivo na área de trabalho.

Os dados ficam no arquivo `data\outreaches.db`.

## Backup e restauração

Na página **Backup**, baixe periodicamente uma cópia e guarde-a em local seguro, preferencialmente fora deste computador. O backup contém dados pessoais e histórico de contatos.

Para restaurar, pare o sistema com `Ctrl+C`. Na pasta `data`, renomeie `outreaches.db` para preservar a versão atual. Copie o arquivo de backup para essa pasta e renomeie a cópia para `outreaches.db`. Inicie o sistema novamente e confira os dados. A restauração volta os dados ao momento da criação do backup; alterações posteriores não estarão nele. Não substitua o arquivo com o sistema aberto.

## Como usar

- Importe uma planilha `.xlsx` ou `.csv` com os nomes dos alunos e, opcionalmente, telefones e e-mails. Selecione as colunas na prévia. Para o WhatsApp, inclua o código do país; ele não é acrescentado nem verificado automaticamente. O sufixo decimal `.0` de números inteiros é removido. Linhas com caracteres inválidos no telefone ou e-mail inválido são informadas e ignoradas. Nomes já ativos são ignorados sem alterar seus cadastros.
- Preencha ou corrija o telefone e o e-mail de cada aluno na tela **Alunos** quando necessário.
- Crie um outreach e use `{nome}` onde a mensagem deve incluir o primeiro nome do aluno.
- Em um outreach, use **Abrir no WhatsApp** para abrir a conversa no aplicativo WhatsApp Desktop instalado no Windows. A alternativa Web permanece disponível no menu **Mais**. Confirme o envio no próprio WhatsApp e então marque o aluno como enviado no sistema.
- Enquanto o outreach estiver **Em andamento**, alunos adicionados posteriormente serão incluídos nele automaticamente. Ao fim da semana, clique em **Encerrar outreach** para preservar sua lista de destinatários.
- Nas metas da semana, selecione o aluno para registrar cada contato. O mesmo aluno pode aparecer em atividades diferentes; cada aluno conta uma vez por atividade da semana. Os registros antigos sem aluno identificado permanecem no total. Esses registros são manuais e independentes do estado dos outreaches.

O sistema nunca envia mensagens sozinho.

Por padrão, a chave de sessão é gerada ao iniciar o sistema. Ao reiniciar, atualize as páginas abertas antes de enviar formulários. Para manter a sessão entre reinícios, configure a variável de ambiente `OUTREACHES_SECRET` com uma chave longa e aleatória, mantida em segredo.

## Testes

Com o ambiente virtual ativado e as dependências instaladas, execute antes de cada alteração:

```powershell
python -m unittest discover -s tests -v
```

Os testes usam um banco SQLite em memória e não alteram os dados locais.
