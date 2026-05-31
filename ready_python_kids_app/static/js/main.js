function escapeHtml(value) {
  return String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function renumberBlocks(){
  document.querySelectorAll('#blocks .block-editor').forEach((el, idx) => {
    el.querySelectorAll('[data-name]').forEach(input => input.name = input.dataset.name.replace('__i__', idx));
  });
  const count = document.getElementById('blocks_count');
  if(count) count.value = document.querySelectorAll('#blocks .block-editor').length;
}

function wrapSelection(textarea, before, after) {
  if (!textarea) return;
  const start = textarea.selectionStart || 0;
  const end = textarea.selectionEnd || 0;
  const value = textarea.value;
  const selected = value.substring(start, end) || 'выделенный текст';
  textarea.value = value.substring(0, start) + before + selected + after + value.substring(end);
  textarea.focus();
  textarea.selectionStart = start + before.length;
  textarea.selectionEnd = start + before.length + selected.length;
}

function formatTextBlock(button, type) {
  const editor = button.closest('.block-editor');
  const textarea = editor.querySelector('textarea[data-name]');
  const map = {
    blue: ['<span class="accent-text">', '</span>'],
    bold: ['<strong>', '</strong>'],
    purple: ['<span class="purple-text">', '</span>'],
    mark: ['<span class="mark-text">', '</span>']
  };
  const pair = map[type];
  if (pair) wrapSelection(textarea, pair[0], pair[1]);
}

function addBlock(type, data={}){
  const wrap = document.createElement('div');
  wrap.className = 'block-editor';

  let body = '';
  if(type === 'text') {
    body = `
      <div class="text-format-toolbar">
        <button type="button" onclick="formatTextBlock(this, 'bold')">Жирный</button>
        <button type="button" onclick="formatTextBlock(this, 'blue')">Синий акцент</button>
        <button type="button" onclick="formatTextBlock(this, 'purple')">Фиолетовый акцент</button>
        <button type="button" onclick="formatTextBlock(this, 'mark')">Выделить фоном</button>
      </div>
      <textarea data-name="block_content___i__" placeholder="Введите текст лекции">${escapeHtml(data.content || '')}</textarea>
      <p class="hint">Выделите часть текста в поле и нажмите кнопку форматирования.</p>`;
  }
  if(type === 'code') {
    body = `<textarea class="code-input" data-name="block_content___i__" placeholder="Введите пример кода">${escapeHtml(data.content || '')}</textarea>`;
  }
  if(type === 'image') {
    body = `<input type="hidden" data-name="block_old_src___i__" value="${escapeHtml(data.src || '')}">
      <input type="file" data-name="block_image___i__" accept="image/*">
      <input data-name="block_caption___i__" placeholder="Подпись к картинке" value="${escapeHtml(data.caption || '')}">
      ${data.src ? `<p class="hint">Текущая картинка: ${escapeHtml(data.src)}</p>` : ''}`;
  }

  wrap.innerHTML = `
    <input type="hidden" data-name="block_type___i__" value="${type}">
    <div class="block-head">
      <strong>${type==='text'?'Текст':type==='code'?'Код':'Картинка'}</strong>
      <div>
        <button type="button" onclick="this.closest('.block-editor').previousElementSibling?.before(this.closest('.block-editor')); renumberBlocks()">Вверх</button>
        <button type="button" onclick="this.closest('.block-editor').nextElementSibling?.after(this.closest('.block-editor')); renumberBlocks()">Вниз</button>
        <button type="button" onclick="this.closest('.block-editor').remove(); renumberBlocks()">Удалить</button>
      </div>
    </div>
    ${body}`;
  document.getElementById('blocks').appendChild(wrap);
  renumberBlocks();
}

function prepareBlocks(){ renumberBlocks(); }

function renumberQuestions(){
  document.querySelectorAll('#questions .question-editor').forEach((el, idx) => {
    el.querySelector('.q-title').textContent = `Вопрос ${idx+1}`;
    el.querySelectorAll('[data-name]').forEach(input => input.name = input.dataset.name.replace('__q__', idx));
  });
  const count = document.getElementById('questions_count');
  if(count) count.value = document.querySelectorAll('#questions .question-editor').length;
}

function addQuestion(data={}){
  const q = document.createElement('div');
  q.className = 'question-editor';

  const questionText = data.question_text || '';
  const answersData = data.answers || [];
  let correctIndex = 0;
  answersData.forEach((a, idx) => {
    if (a.is_correct) correctIndex = idx;
  });

  let answers = '';
  for(let i=0;i<4;i++){
    const answer = answersData[i] || {};
    answers += `
      <div class="answer-row">
        <input data-name="answer___q___${i}" placeholder="Вариант ответа ${i+1}" value="${escapeHtml(answer.answer_text || '')}">
        <label><input type="radio" data-name="correct___q__" value="${i}" ${i===correctIndex?'checked':''}> правильный</label>
        <input data-name="hint___q___${i}" placeholder="Подсказка, если выбран этот неверный ответ" value="${escapeHtml(answer.hint || '')}">
      </div>`;
  }

  q.innerHTML = `
    <div class="block-head">
      <strong class="q-title">Вопрос</strong>
      <button type="button" onclick="this.closest('.question-editor').remove(); renumberQuestions()">Удалить</button>
    </div>
    <textarea data-name="question___q__" placeholder="Текст вопроса" required>${escapeHtml(questionText)}</textarea>
    ${answers}`;

  document.getElementById('questions').appendChild(q);
  renumberQuestions();
}

function prepareQuestions(){ renumberQuestions(); }
