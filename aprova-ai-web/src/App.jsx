import React, { useState, useEffect, useRef } from 'react';

// Caso queira usar Markdown completo como no seu HTML, o marked funciona perfeitamente no React
// Certifique-se de instalar rodando no terminal: npm install marked
import { marked } from 'marked';
import html2pdf from 'html2pdf.js';

// Configurações do marked idênticas ao seu HTML
marked.setOptions({ breaks: true, gfm: true });

// Faz todos os links (ex.: das vagas) abrirem em uma nova aba com segurança.
const abrirLinksEmNovaAba = (html) =>
  html.replace(/<a\s+(?![^>]*\btarget=)/gi, '<a target="_blank" rel="noopener noreferrer" ');

export default function App() {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'bot',
      content: 'Olá! Eu sou o <strong>AprovaAI</strong>. Posso buscar vagas de concursos de TI, montar cronogramas de estudo por banca e tirar suas dúvidas estratégicas. Como posso te ajudar hoje?',
      isHtml: true // Para a mensagem inicial que já tem tags HTML prontas
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [online, setOnline] = useState(true);
  const [arquivos, setArquivos] = useState([]);
  const [view, setView] = useState('chat'); // 'chat' | 'estudos'
  const [estudos, setEstudos] = useState({ planos: [], simulados: [] });
  const [carregandoEstudos, setCarregandoEstudos] = useState(false);

  const chatRef = useRef(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);

  const API = 'http://localhost:8000';

  const carregarEstudos = async () => {
    setCarregandoEstudos(true);
    try {
      const [rPlanos, rSimulados] = await Promise.all([
        fetch(`${API}/api/planos`),
        fetch(`${API}/api/simulados`),
      ]);
      const dPlanos = await rPlanos.json().catch(() => ({ planos: [] }));
      const dSimulados = await rSimulados.json().catch(() => ({ simulados: [] }));
      setEstudos({ planos: dPlanos.planos || [], simulados: dSimulados.simulados || [] });
    } catch (e) {
      setEstudos({ planos: [], simulados: [] });
    } finally {
      setCarregandoEstudos(false);
    }
  };

  const abrirEstudos = () => {
    setView('estudos');
    carregarEstudos();
  };

  // Apaga um item (plano ou simulado) do histórico.
  const apagarEstudo = async (tipo, id) => {
    const rotulo = tipo === 'simulados' ? 'este simulado' : 'este plano';
    if (!window.confirm(`Apagar ${rotulo}? Esta ação não pode ser desfeita.`)) return;
    try {
      const r = await fetch(`${API}/api/${tipo}/${id}`, { method: 'DELETE' });
      if (!r.ok) throw new Error('Falha ao apagar.');
      setEstudos((prev) => ({
        ...prev,
        [tipo]: prev[tipo].filter((item) => item.id !== id),
      }));
    } catch (e) {
      window.alert('Não foi possível apagar. Verifique se o servidor está rodando.');
    }
  };

  // Apaga TODO o histórico (planos + simulados).
  const apagarTodosEstudos = async () => {
    if (!window.confirm('Apagar TODO o histórico de planos e simulados? Esta ação não pode ser desfeita.')) return;
    try {
      await Promise.all([
        fetch(`${API}/api/planos`, { method: 'DELETE' }),
        fetch(`${API}/api/simulados`, { method: 'DELETE' }),
      ]);
      setEstudos({ planos: [], simulados: [] });
    } catch (e) {
      window.alert('Não foi possível apagar o histórico. Verifique se o servidor está rodando.');
    }
  };

  const TIPOS_ACEITOS = '.pdf,image/png,image/jpeg,image/webp,image/gif';

  const handleSelecionarArquivos = (e) => {
    const novos = Array.from(e.target.files || []);
    setArquivos((prev) => [...prev, ...novos]);
    e.target.value = ''; // permite re-selecionar o mesmo arquivo
  };

  const removerArquivo = (index) => {
    setArquivos((prev) => prev.filter((_, i) => i !== index));
  };

  // Auto-scroll automático sempre que uma nova mensagem chegar
  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [messages, loading]);

  // Ajusta a altura do textarea conforme o Toni digita
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 160) + 'px';
    }
  }, [input]);

  const escapeHtml = (string) => {
    return string.replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  };

  const handleSendMessage = async (textToSend) => {
    const text = textToSend || input;
    const anexos = arquivos;
    // Precisa de texto OU de pelo menos um arquivo anexado
    if ((!text.trim() && anexos.length === 0) || loading) return;

    // 1. Adiciona a mensagem do Toni na tela (com os nomes dos anexos, se houver)
    const userMessageId = Date.now().toString();
    const nomesAnexos = anexos.map((a) => `📎 ${a.name}`).join('<br>');
    const conteudoUsuario = [escapeHtml(text), nomesAnexos].filter(Boolean).join('<br>');
    setMessages((prev) => [...prev, { id: userMessageId, role: 'user', content: conteudoUsuario, isHtml: true }]);
    setInput('');
    setArquivos([]);

    setLoading(true);

    try {
      let response;
      if (anexos.length > 0) {
        // Envio com arquivos: usa multipart/form-data (sem Content-Type manual)
        const formData = new FormData();
        formData.append('mensagem', text);
        anexos.forEach((arquivo) => formData.append('arquivos', arquivo));
        response = await fetch('http://localhost:8000/api/chat-arquivo-stream', {
          method: 'POST',
          body: formData,
        });
      } else {
        response = await fetch('http://localhost:8000/api/chat-stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mensagem: text }),
        });
      }

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        setMessages((prev) => [
          ...prev,
          { id: Date.now().toString(), role: 'bot', content: `⚠️ Erro ${response.status}: ${escapeHtml(err.detail || "falha na requisição")}`, isHtml: false }
        ]);
      } else {
        // Resposta em streaming.
        // Enquanto chega, mostramos TEXTO SIMPLES (Markdown incompleto renderiza quebrado);
        // ao finalizar, convertemos o Markdown completo de uma só vez (formatação correta).
        const botMessageId = `bot-${Date.now()}`;
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let acumulado = '';
        let bolhaIniciada = false;

        const atualizarBolha = (html, raw) => {
          if (!bolhaIniciada) {
            bolhaIniciada = true;
            setLoading(false);
            setMessages((prev) => [...prev, { id: botMessageId, role: 'bot', content: html, isHtml: true, raw }]);
          } else {
            setMessages((prev) =>
              prev.map((m) => (m.id === botMessageId ? { ...m, content: html, raw } : m))
            );
          }
        };

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          acumulado += decoder.decode(value, { stream: true });
          // Prévia em texto simples (escapado), preservando quebras de linha.
          atualizarBolha(`<span class="streaming-preview">${escapeHtml(acumulado)}</span>`, acumulado);
        }
        acumulado += decoder.decode(); // descarrega bytes finais pendentes

        // Formatação final do Markdown completo, com links em nova aba.
        // Guardamos também o Markdown bruto (raw) para permitir baixar/copiar.
        const htmlFinal = abrirLinksEmNovaAba(marked.parse(acumulado || 'Sem resposta.'));
        atualizarBolha(htmlFinal, acumulado);
      }
    } catch (error) {
      setMessages((prev) => [
        ...prev, 
        { id: Date.now().toString(), role: 'bot', content: "⚠️ Não consegui falar com o servidor. Ele está rodando?", isHtml: false }
      ]);
      setOnline(false);
    } finally {
      setLoading(false);
      setTimeout(() => textareaRef.current?.focus(), 50);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const chips = [
    "Quero ver vagas de concurso para desenvolvedor",
    "Monte um cronograma de estudos para a banca CEBRASPE",
    "Como priorizar matérias para concurso de TI?"
  ];

  // Detecta se uma resposta é um simulado (questões + gabarito).
  const ehSimulado = (raw) => {
    if (!raw) return false;
    const texto = raw.toLowerCase();
    return texto.includes('gabarito') || (texto.includes('simulado') && texto.includes('questão'));
  };

  // Detecta se uma resposta é um plano/cronograma de estudos (para exibir o botão de exportar).
  const ehPlano = (raw) => {
    if (!raw) return false;
    const texto = raw.toLowerCase();
    const temPlano = texto.includes('cronograma') || texto.includes('plano de estudo');
    const temSemanas = (texto.match(/semana\s*\d+/g) || []).length >= 2;
    const temTabela = (raw.match(/\|/g) || []).length >= 6;
    return temPlano && (temSemanas || temTabela);
  };

  // Limpa o Markdown removendo linhas de tabela quebradas no fim e excesso de quebras.
  const limparMarkdown = (texto) => {
    let linhas = texto.split('\n').map((l) => l.replace(/\s+$/, ''));
    while (linhas.length) {
      const ultima = linhas[linhas.length - 1].trim();
      if (ultima === '' || /^[|:\-\s]+$/.test(ultima)) linhas.pop();
      else break;
    }
    return linhas.join('\n').replace(/\n{3,}/g, '\n\n').trim();
  };

  // Gera o nome do arquivo a partir do primeiro título do Markdown.
  const nomeArquivoPlano = (raw) => {
    const linha = raw.split('\n').find((l) => l.trim().startsWith('#'));
    const base = (linha ? linha.replace(/[#*`]/g, '') : 'plano_de_estudos')
      .trim()
      .toLowerCase()
      .replace(/[\\/*?:"<>|]/g, '')
      .replace(/\s+/g, '_')
      .slice(0, 60);
    return `plano_${base || 'estudos'}.md`;
  };

  const exportarPlano = (raw) => {
    const conteudo = limparMarkdown(raw || '');
    const blob = new Blob([conteudo], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = nomeArquivoPlano(conteudo);
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const exportarPlanoPDF = (raw) => {
    const conteudo = limparMarkdown(raw || '');
    const corpoHtml = marked.parse(conteudo);

    // Documento com tema claro para um PDF limpo e legível (independente do tema do app).
    const container = document.createElement('div');
    container.innerHTML = `
      <div style="font-family: 'Segoe UI', Arial, sans-serif; color: #1a1a1a; padding: 24px; font-size: 13px; line-height: 1.55;">
        ${corpoHtml}
      </div>`;
    // Estiliza tabelas para o PDF
    container.querySelectorAll('table').forEach((t) => {
      t.style.borderCollapse = 'collapse';
      t.style.width = '100%';
      t.style.margin = '10px 0';
    });
    container.querySelectorAll('th, td').forEach((c) => {
      c.style.border = '1px solid #999';
      c.style.padding = '6px 9px';
      c.style.textAlign = 'left';
      c.style.fontSize = '12px';
    });
    container.querySelectorAll('th').forEach((c) => { c.style.background = '#eef'; });
    // Gabarito/comentário (blockquote) em verde também no PDF
    container.querySelectorAll('blockquote').forEach((b) => {
      b.style.borderLeft = '4px solid #1a7f4b';
      b.style.background = '#eafaf0';
      b.style.color = '#0f6b39';
      b.style.margin = '8px 0';
      b.style.padding = '6px 12px';
      b.style.borderRadius = '6px';
    });

    const nomePdf = nomeArquivoPlano(conteudo).replace(/\.md$/, '.pdf');
    const opcoes = {
      margin: [10, 10, 12, 10],
      filename: nomePdf,
      image: { type: 'jpeg', quality: 0.98 },
      html2canvas: { scale: 2, useCORS: true, backgroundColor: '#ffffff' },
      jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
      pagebreak: { mode: ['avoid-all', 'css', 'legacy'] },
    };
    html2pdf().set(opcoes).from(container).save();
  };

  return (
    <div className="app">
      {/* HEADER */}
      <header>
        <div className="logo">🤖</div>
        <div>
          <h1>AprovaAI</h1>
          <p>Mentor de estudos com IA para concursos de TI</p>
        </div>
        <div className="status">
          <span className={`dot ${!online ? 'off' : ''}`} id="statusDot"></span>
          <span id="statusText">{online ? 'conectado' : 'offline'}</span>
        </div>
      </header>

      {/* ABAS DE NAVEGAÇÃO */}
      <nav className="tabs">
        <button
          className={`tab ${view === 'chat' ? 'active' : ''}`}
          onClick={() => setView('chat')}
        >
          💬 Chat
        </button>
        <button
          className={`tab ${view === 'estudos' ? 'active' : ''}`}
          onClick={abrirEstudos}
        >
          📚 Meus Estudos
        </button>
      </nav>

      {view === 'estudos' && (
        <div className="estudos">
          <div className="estudos-header">
            <h2>📚 Meus Estudos</h2>
            <div className="estudos-acoes">
              <button className="export-btn" onClick={carregarEstudos} disabled={carregandoEstudos}>
                {carregandoEstudos ? 'Atualizando...' : '↻ Atualizar'}
              </button>
              {(estudos.planos.length > 0 || estudos.simulados.length > 0) && (
                <button className="export-btn danger" onClick={apagarTodosEstudos}>
                  🗑 Apagar tudo
                </button>
              )}
            </div>
          </div>

          {carregandoEstudos && <p className="estudos-vazio">Carregando...</p>}

          {!carregandoEstudos && estudos.planos.length === 0 && estudos.simulados.length === 0 && (
            <p className="estudos-vazio">
              Você ainda não tem planos nem simulados salvos. Gere um no chat e eles aparecerão aqui.
            </p>
          )}

          {!carregandoEstudos && estudos.simulados.length > 0 && (
            <section>
              <h3 className="estudos-secao">📝 Simulados ({estudos.simulados.length})</h3>
              {estudos.simulados.map((s) => (
                <details className="estudo-card" key={`sim-${s.id}`}>
                  <summary>
                    <strong>{s.concurso}</strong>
                    <span className="estudo-meta">Banca: {s.banca} · {s.criado_em}</span>
                  </summary>
                  <div
                    className="bubble simulado"
                    dangerouslySetInnerHTML={{ __html: abrirLinksEmNovaAba(marked.parse(s.conteudo || '')) }}
                  />
                  <div className="export-actions">
                    <button className="export-btn" onClick={() => exportarPlanoPDF(s.conteudo)}>⬇ PDF</button>
                    <button className="export-btn" onClick={() => exportarPlano(s.conteudo)}>⬇ Markdown (.md)</button>
                    <button className="export-btn danger" onClick={() => apagarEstudo('simulados', s.id)}>🗑 Apagar</button>
                  </div>
                </details>
              ))}
            </section>
          )}

          {!carregandoEstudos && estudos.planos.length > 0 && (
            <section>
              <h3 className="estudos-secao">🎯 Planos de estudo ({estudos.planos.length})</h3>
              {estudos.planos.map((p) => (
                <details className="estudo-card" key={`plano-${p.id}`}>
                  <summary>
                    <strong>{p.concurso}</strong>
                    <span className="estudo-meta">Banca: {p.banca} · {p.criado_em}</span>
                  </summary>
                  <div
                    className="bubble"
                    dangerouslySetInnerHTML={{ __html: abrirLinksEmNovaAba(marked.parse(p.cronograma || '')) }}
                  />
                  <div className="export-actions">
                    <button className="export-btn" onClick={() => exportarPlanoPDF(p.cronograma)}>⬇ PDF</button>
                    <button className="export-btn" onClick={() => exportarPlano(p.cronograma)}>⬇ Markdown (.md)</button>
                    <button className="export-btn danger" onClick={() => apagarEstudo('planos', p.id)}>🗑 Apagar</button>
                  </div>
                </details>
              ))}
            </section>
          )}
        </div>
      )}

      {view === 'chat' && (
      <>
      {/* CHAT CONTAINER */}
      <div className="chat" id="chat" ref={chatRef}>
        {messages.map((msg) => (
          <div key={msg.id} className={`msg ${msg.role}`}>
            <div className={`avatar ${msg.role}`}>
              {msg.role === 'user' ? '🧑' : '🤖'}
            </div>
            <div className="bubble-wrap">
              {msg.isHtml ? (
                <div
                  className={`bubble ${msg.role === 'bot' && ehSimulado(msg.raw) ? 'simulado' : ''}`}
                  dangerouslySetInnerHTML={{ __html: msg.content }}
                />
              ) : (
                <div className="bubble">{msg.content}</div>
              )}
              {msg.role === 'bot' && (ehPlano(msg.raw) || ehSimulado(msg.raw)) && (
                <div className="export-actions">
                  <button
                    className="export-btn"
                    title="Baixar em PDF"
                    onClick={() => exportarPlanoPDF(msg.raw)}
                  >
                    ⬇ Baixar PDF
                  </button>
                  <button
                    className="export-btn"
                    title="Baixar em Markdown (.md)"
                    onClick={() => exportarPlano(msg.raw)}
                  >
                    ⬇ Markdown (.md)
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}

        {/* LOADING / TYPING ANIMATION */}
        {loading && (
          <div className="msg bot">
            <div className="avatar bot">🤖</div>
            <div className="bubble">
              <div className="typing">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* SUGGESTIONS CHIPS */}
      {messages.length <= 1 && !loading && (
        <div className="suggestions" id="suggestions">
          {chips.map((chipText, index) => (
            <div 
              key={index} 
              className="chip" 
              onClick={() => handleSendMessage(chipText)}
            >
              {chipText}
            </div>
          ))}
        </div>
      )}

      {/* ARQUIVOS ANEXADOS */}
      {arquivos.length > 0 && (
        <div className="anexos">
          {arquivos.map((arquivo, index) => (
            <div className="anexo-chip" key={`${arquivo.name}-${index}`}>
              <span className="anexo-icon">{arquivo.type.startsWith('image/') ? '🖼️' : '📄'}</span>
              <span className="anexo-nome" title={arquivo.name}>{arquivo.name}</span>
              <button
                className="anexo-remover"
                title="Remover anexo"
                onClick={() => removerArquivo(index)}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      {/* INPUT / COMPOSER */}
      <div className="composer">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={TIPOS_ACEITOS}
          style={{ display: 'none' }}
          onChange={handleSelecionarArquivos}
        />
        <button
          className="attach"
          title="Anexar edital (PDF) ou imagem"
          onClick={() => fileInputRef.current?.click()}
          disabled={loading}
        >
          📎
        </button>
        <textarea
          ref={textareaRef}
          id="input"
          rows="1"
          placeholder="Escreva sua mensagem ou anexe um edital/imagem..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button 
          className="send" 
          id="send" 
          title="Enviar"
          onClick={() => handleSendMessage()}
          disabled={loading || (!input.trim() && arquivos.length === 0)}
        >
          ➤
        </button>
      </div>
      </>
      )}
    </div>
  );
}