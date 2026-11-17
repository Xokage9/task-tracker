'use strict';

const icons = {
  check:'<path d="m5 12 4 4L19 6"/>', grid:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  board:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16M15 4v16"/>', plus:'<path d="M12 5v14M5 12h14"/>',
  bell:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>', chart:'<path d="M4 3v18h17M9 16v-5M14 16V6M19 16v-8"/>',
  settings:'<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="15" cy="17" r="3"/>', search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>', calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/>',
  close:'<path d="m6 6 12 12M6 18 18 6"/>', user:'<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
  logout:'<path d="M9 4H4v16h5M9 12h12m-5-5 5 5-5 5"/>', download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  trash:'<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/>', menu:'<path d="M4 6h16M4 12h16M4 18h16"/>',
  arrow:'<path d="M5 12h14m-6-6 6 6-6 6"/>', refresh:'<path d="M20 7a9 9 0 1 0 1 8M20 3v5h-5"/>', folder:'<path d="M3 7V4h6l3 3h9v13H3z"/>',
};
const icon = (name) => `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.grid}</svg>`;
const e = (value) => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const statuses = {todo:'К работе', in_progress:'В работе', review:'На проверке', done:'Готово'};
const priorities = {low:'Низкий', medium:'Средний', high:'Высокий'};
const state = {token:sessionStorage.getItem('tracker-token'), user:null, projects:[], project:null, members:[], tasks:[], view:'board', query:'', priority:'', mine:false, unread:0, notifications:null, notificationPage:0, report:null, loading:false, error:'', authMode:'login', epoch:0};
const app = document.querySelector('#app');
const modal = document.querySelector('#modal');
let modalVersion = 0;
let toastTimer;

function toast(message) {
  const target = document.querySelector('#toast');
  target.textContent = message;
  target.classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => target.classList.remove('visible'), 4000);
}

async function api(path, options={}) {
  let response;
  try {
    response = await fetch(path, {cache:'no-store', ...options, headers:{
      ...(options.body ? {'Content-Type':'application/json'} : {}),
      ...(state.token ? {Authorization:`Bearer ${state.token}`} : {}), ...options.headers,
    }});
  } catch { throw new Error('Нет связи с сервером. Попробуйте ещё раз.'); }
  if (!response.ok) {
    let data = {};
    try { data = await response.json(); } catch { /* Non-JSON gateway errors. */ }
    if (response.status === 401 && !path.endsWith('/login')) {
      logout();
      throw new Error('Сеанс истёк. Войдите ещё раз.');
    }
    const message = Array.isArray(data.detail) ? 'Проверьте заполненные поля.' : data.detail;
    throw new Error(message || `Сервис временно недоступен (${response.status}).`);
  }
  if (options.raw) return response;
  return response.status === 204 ? null : response.json();
}
const post = (path, data, method='POST') => api(path, {method, body:JSON.stringify(data)});
async function allPages(path) {
  const items = [];
  for (let offset=0;;offset+=200) {
    const page = await api(`${path}${path.includes('?') ? '&' : '?'}limit=200&offset=${offset}`);
    items.push(...page);
    if (page.length < 200) return items;
  }
}
function initials(name) { return String(name || '?').trim().split(/\s+/).slice(0,2).map(part => Array.from(part)[0]).join('').toUpperCase(); }
function avatar(user, extra='') { return user ? `<span class="avatar ${extra}" title="${e(user.name)}">${e(initials(user.name))}</span>` : `<span class="avatar unassigned" title="Без исполнителя">${icon('user')}</span>`; }
function userById(id) { return state.members.find(user => user.id === id); }
function dateValue(value) { return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : value+'Z'); }
function dateLabel(value) { return value ? new Date(value+'T12:00:00').toLocaleDateString('ru-RU', {day:'numeric', month:'short'}) : 'Без срока'; }
function timeLabel(value) { return value ? dateValue(value).toLocaleString('ru-RU', {day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}) : ''; }
function overdue(task) { return task.due_date && task.due_date < new Date().toISOString().slice(0,10) && task.status !== 'done'; }
function logo() { return `<div class="logo"><span class="logo-mark">${icon('check')}</span>трек<span class="muted">.</span></div>`; }
function options(map, current) { return Object.entries(map).map(([key,label]) => `<option value="${key}" ${key===current?'selected':''}>${label}</option>`).join(''); }

function renderAuth() {
  const register = state.authMode === 'register';
  app.innerHTML = `<main class="auth-page"><aside class="auth-aside">${logo()}<h1>Меньше хаоса.<br>Больше сделанного.</h1><p>Планируйте задачи, обсуждайте идеи и двигайтесь к цели вместе с командой.</p><div class="auth-kicker">Одно пространство для ваших проектов</div></aside>
    <section class="auth-main"><div class="auth-box"><h2>${register?'Начнём новый проект':'С возвращением'}</h2><p>${register?'Создайте аккаунт и соберите свою команду.':'Ваши проекты и задачи уже ждут вас.'}</p><form id="auth-form">
      ${register?'<div class="form-field"><label for="name">Как вас зовут</label><input id="name" name="name" autocomplete="name" maxlength="100" required placeholder="Антон"></div>':''}
      <div class="form-field"><label for="email">Email</label><input id="email" name="email" type="email" autocomplete="email" maxlength="254" required placeholder="you@example.com"></div>
      <div class="form-field"><label for="password">Пароль</label><input id="password" name="password" type="password" autocomplete="${register?'new-password':'current-password'}" minlength="${register?8:1}" maxlength="128" required placeholder="${register?'Не меньше 8 символов':'Введите пароль'}"></div>
      <div class="form-error" role="alert"></div><button class="btn primary" type="submit">${register?'Создать аккаунт':'Войти в пространство'} ${icon('arrow')}</button></form>
      <div class="auth-switch">${register?'Уже есть аккаунт?':'Первый раз здесь?'} <button class="link" data-action="auth-switch">${register?'Войти':'Создать аккаунт'}</button></div></div></section></main>`;
}

function render() {
  if (!state.user) return renderAuth();
  const project = state.project;
  const owner = project?.owner_id === state.user.id;
  app.innerHTML = `<div class="shell"><aside class="sidebar" id="sidebar">${logo()}
    <div class="workspace"><span class="workspace-icon">${e(initials(state.user.name).slice(0,1))}</span><div><div class="user-name">Моё пространство</div><div class="small muted">Работаем вместе</div></div></div>
    <nav aria-label="Основная навигация"><button class="nav-item ${state.view==='board'?'active':''}" data-view="board">${icon('board')} Мои задачи</button><button class="nav-item ${state.view==='reports'?'active':''}" data-view="reports">${icon('chart')} Отчёты</button><button class="nav-item ${state.view==='notifications'?'active':''}" data-view="notifications">${icon('bell')} Уведомления <span class="badge" id="nav-unread" ${state.unread?'':'hidden'}>${state.unread}</span></button></nav>
    <div class="sidebar-label row spread"><span>Проекты</span><button class="icon-btn" data-action="new-project" title="Создать проект" aria-label="Создать проект">${icon('plus')}</button></div>
    <div class="project-list">${state.projects.map(p => `<button class="project-link ${p.id===project?.id?'active':''}" data-project="${p.id}"><span class="project-dot"></span><span>${e(p.name)}</span></button>`).join('') || '<p class="small muted" style="padding:10px 13px">Пока ни одного проекта</p>'}</div>
    <div class="sidebar-bottom"><div class="user-bar">${avatar(state.user)}<div class="grow"><div class="user-name">${e(state.user.name)}</div><div class="small muted">Личное пространство</div></div><button class="icon-btn" data-action="logout" title="Выйти" aria-label="Выйти">${icon('logout')}</button></div></div></aside>
    <main class="main"><header class="topbar"><div class="row"><button class="icon-btn mobile-menu" data-action="menu" aria-label="Открыть меню">${icon('menu')}</button><div class="breadcrumbs">Рабочее пространство <span>/</span> <strong>${e(state.view==='notifications'?'Уведомления':project?.name || 'Проекты')}</strong></div></div><div class="top-right"><span class="today">${new Date().toLocaleDateString('ru-RU',{day:'numeric',month:'long',weekday:'short'})}</span><button class="icon-btn bell" data-view="notifications" title="Уведомления" aria-label="Уведомления">${icon('bell')}<span class="badge" id="bell-unread" ${state.unread?'':'hidden'}>${state.unread}</span></button>${avatar(state.user,'green')}</div></header>
    <section class="content"><div class="page-heading"><div><div class="eyebrow">${state.view==='notifications'?'Всегда в курсе':'Ваш следующий шаг'}</div><h1>${e(state.view==='notifications'?'Уведомления':project?.name || 'Ваши проекты')}</h1><p>${e(state.view==='notifications'?'Всё, что изменилось в ваших проектах.':project?.description || 'Соберите задачи в одном месте и сосредоточьтесь на главном.')}</p></div>
      ${state.view==='notifications'?'<button class="btn" data-action="read-all">'+icon('check')+' Прочитать всё</button>':project?'<button class="btn primary" data-action="new-task">'+icon('plus')+' Новая задача</button>':'<button class="btn primary" data-action="new-project">'+icon('plus')+' Новый проект</button>'}</div>
    ${project && state.view!=='notifications' ? statsHTML()+`<div class="viewbar"><div class="tabs"><button class="tab ${state.view==='board'?'active':''}" data-view="board">${icon('board')} Доска задач</button><button class="tab ${state.view==='reports'?'active':''}" data-view="reports">${icon('chart')} Отчёт</button><button class="tab ${state.view==='settings'?'active':''}" data-view="settings">${icon('settings')} ${owner?'Настройки':'Участники'}</button></div><span class="viewbar-note">${state.members.length} в команде · ${state.tasks.length} задач</span></div>`:''}
    <div id="view">${viewHTML()}</div></section></main></div>`;
}

function statsHTML() {
  const stats = [
    ['grid',state.tasks.length,'Всего задач'],['clock',state.tasks.filter(t=>t.status==='in_progress').length,'В работе'],
    ['check',state.tasks.filter(t=>t.status==='done').length,'Завершено'],['calendar',state.tasks.filter(overdue).length,'Просрочено'],
  ];
  return `<div class="stats">${stats.map(([i,value,label])=>`<div class="stat"><div class="stat-icon">${icon(i)}</div><div><div class="stat-value">${value}</div><div class="stat-label">${label}</div></div></div>`).join('')}</div>`;
}
function emptyHTML(title, message, action='new-project', button='Создать проект') {
  return `<div class="empty"><div class="empty-symbol">${icon('folder')}</div><h2>${e(title)}</h2><p>${e(message)}</p><button class="btn primary" data-action="${action}">${icon('plus')} ${e(button)}</button></div>`;
}
function viewHTML() {
  if (state.loading) return '<div class="loading">Загружаем данные…</div>';
  if (state.error) return `<div class="error-panel">${e(state.error)} <button class="link" data-action="refresh">Повторить</button></div>`;
  if (state.view==='notifications') return notificationsHTML();
  if (!state.project) return emptyHTML('Начните с проекта','Создайте первый проект, добавьте задачи и пригласите коллег.');
  if (state.view==='reports') return reportsHTML();
  if (state.view==='settings') return settingsHTML();
  return `<div class="filters"><div class="search">${icon('search')}<input id="search" aria-label="Поиск задач" placeholder="Найти задачу…" value="${e(state.query)}" maxlength="200"></div><select id="priority-filter" aria-label="Фильтр по приоритету"><option value="">Все приоритеты</option>${options(priorities,state.priority)}</select><button class="btn filter-toggle ${state.mine?'active':''}" data-action="mine">${icon('user')} Мои задачи</button><span class="count-label" id="filtered-count"></span></div><div id="board" class="board">${boardHTML()}</div>`;
}
function filteredTasks() {
  return state.tasks.filter(task => (!state.query || task.title.toLowerCase().includes(state.query.toLowerCase())) && (!state.priority || task.priority===state.priority) && (!state.mine || task.assignee_id===state.user.id));
}
function boardHTML() {
  const tasks = filteredTasks();
  return Object.entries(statuses).map(([status,label]) => {
    const group = tasks.filter(task => task.status===status);
    return `<section class="column ${status}" aria-label="${label}"><div class="column-head"><span class="status-dot"></span>${label}<span class="column-count">${group.length}</span><button class="icon-btn" data-action="new-task" data-status="${status}" title="Добавить задачу" aria-label="Добавить задачу: ${label}">${icon('plus')}</button></div>${group.map(taskCard).join('') || '<div class="column-empty">Здесь пока свободно</div>'}<button class="add-task" data-action="new-task" data-status="${status}">${icon('plus')} Добавить задачу</button></section>`;
  }).join('');
}
function taskCard(task) {
  return `<button class="task-card" data-task="${task.id}"><div class="card-top"><span class="priority ${task.priority}">${task.priority==='high'?'↗':task.priority==='low'?'↘':'→'} ${priorities[task.priority]}</span><span class="task-id">TSK-${task.id}</span></div><h3 class="task-title">${e(task.title)}</h3>${task.description?`<p class="task-description">${e(task.description)}</p>`:''}<div class="card-bottom"><span class="due ${overdue(task)?'overdue':''}">${icon('calendar')} ${dateLabel(task.due_date)}</span>${avatar(userById(task.assignee_id))}</div></button>`;
}
function updateBoard() {
  const board = document.querySelector('#board');
  if (board) board.innerHTML = boardHTML();
  const count = document.querySelector('#filtered-count');
  if (count) count.textContent = `${filteredTasks().length} из ${state.tasks.length} задач`;
}
function reportsHTML() {
  const report = state.report;
  if (!report) return '<div class="loading">Строим отчёт…</div>';
  return `<div class="row spread" style="margin-bottom:20px"><h2>Проект в цифрах</h2><div class="row"><button class="btn small" data-action="refresh">${icon('refresh')} Обновить</button><button class="btn small" data-action="download-report">${icon('download')} Скачать CSV</button></div></div><div class="report-grid"><div class="panel"><h3>Задачи по статусам</h3>${Object.entries(statuses).map(([key,label])=>`<div class="bar-row"><span>${label}</span><div class="bar-bg"><div class="bar-fill ${key}" style="width:${report.total?report.by_status[key]/report.total*100:0}%"></div></div><span>${report.by_status[key]}</span></div>`).join('')}</div><div class="panel"><h3>Прогресс проекта</h3><div class="progress-number">${report.completion_percent}%</div><div class="bar-bg"><div class="bar-fill done" style="width:${report.completion_percent}%"></div></div><p class="report-note">Завершено ${report.completed} из ${report.total} задач.${report.overdue?' Требуют внимания: '+report.overdue+' просроченных.':' Просроченных задач нет.'}</p></div><div class="panel"><h3>Нагрузка команды · открытые задачи</h3>${report.workload.length?report.workload.map(row=>`<div class="member">${avatar(userById(row.assignee_id))}<span class="grow">${e(userById(row.assignee_id)?.name || 'Без исполнителя')}</span><strong>${row.tasks}</strong></div>`).join(''):'<p class="muted small">Все задачи завершены.</p>'}</div><div class="panel"><h3>Приоритеты</h3>${Object.entries(priorities).map(([key,label])=>`<div class="member"><span class="priority ${key}">${label}</span><span class="grow"></span><strong>${report.by_priority[key]}</strong></div>`).join('')}</div></div><p class="report-updated">Обновлено ${timeLabel(report.generated_at)} · сроки считаются по UTC</p>`;
}
function notificationsHTML() {
  const data = state.notifications;
  if (!data) return '<div class="loading">Загружаем уведомления…</div>';
  if (!data.total) return `<div class="empty"><div class="empty-symbol">${icon('bell')}</div><h2>Вы ничего не пропустили</h2><p>Здесь появятся новые задачи, комментарии и изменения в проектах.</p></div>`;
  return `<div class="notification-list">${data.items.map(item=>`<article class="notification ${item.read_at?'':'unread'}"><div class="stat-icon">${icon(item.kind==='comment.created'?'user':'bell')}</div><div class="grow"><h3>${e(item.title)}</h3><p>${e(item.body)}</p>${item.task_id?`<button class="link small" data-notification-task="${item.task_id}" data-project-id="${item.project_id}" data-event-id="${item.event_id}">Открыть задачу →</button>`:''}</div><time>${timeLabel(item.created_at)}</time>${!item.read_at?`<button class="icon-btn" data-read="${item.event_id}" title="Отметить прочитанным" aria-label="Отметить прочитанным">${icon('check')}</button>`:''}</article>`).join('')}</div><div class="pagination"><button class="btn small" data-page="${state.notificationPage-1}" ${state.notificationPage===0?'disabled':''}>Назад</button><span class="small muted">${state.notificationPage+1} / ${Math.ceil(data.total/30)}</span><button class="btn small" data-page="${state.notificationPage+1}" ${(state.notificationPage+1)*30>=data.total?'disabled':''}>Далее</button></div>`;
}
function settingsHTML() {
  const owner = state.project.owner_id===state.user.id;
  return `<div class="settings-grid"><div class="panel"><h3>О проекте</h3>${owner?`<form id="project-settings" class="stack"><div class="form-field"><label for="project-name">Название</label><input id="project-name" name="name" value="${e(state.project.name)}" required maxlength="150"></div><div class="form-field"><label for="project-description">Описание</label><textarea id="project-description" name="description" maxlength="10000">${e(state.project.description)}</textarea></div><div class="form-error" role="alert"></div><div class="row spread"><button class="btn danger small" type="button" data-action="delete-project">Удалить проект</button><button class="btn primary" type="submit">Сохранить</button></div></form>`:`<p>${e(state.project.description || 'У проекта пока нет описания.')}</p><p class="small muted" style="margin-top:16px">Настройками управляет владелец проекта.</p>`}</div><div class="panel"><h3>Участники · ${state.members.length}</h3>${state.members.map(member=>`<div class="member">${avatar(member)}<div class="grow"><div class="user-name">${e(member.name)} ${member.id===state.project.owner_id?'<span class="small muted">· владелец</span>':''}</div><p>${e(member.email)}</p></div>${owner&&member.id!==state.user.id?`<button class="icon-btn" data-remove-member="${member.id}" title="Исключить участника" aria-label="Исключить участника">${icon('close')}</button>`:''}</div>`).join('')}${owner?`<form id="member-form" class="stack" style="margin-top:20px"><div class="form-field"><label for="member-email">Добавить по email</label><div class="row"><input id="member-email" name="email" type="email" required placeholder="colleague@example.com"><button class="btn" type="submit">${icon('plus')}</button></div><span class="password-note">Коллеге нужно сначала зарегистрироваться.</span></div><div class="form-error" role="alert"></div></form>`:''}</div></div>`;
}

async function selectProject(projectId) {
  const project = state.projects.find(p=>p.id===Number(projectId));
  if (!project) throw new Error('Проект удалён или доступ к нему закрыт.');
  const epoch = ++state.epoch;
  state.project = project;
  state.tasks = []; state.members = []; state.report = null;
  state.loading=true; state.error=''; state.query=''; state.priority=''; state.mine=false;
  if (state.view==='notifications') state.view='board';
  render();
  try {
    const [tasks,members] = await Promise.all([allPages(`/api/tasks?project_id=${project.id}`), api(`/api/projects/${project.id}/members`)]);
    if (epoch!==state.epoch) return;
    state.tasks=tasks; state.members=members; state.loading=false;
    if (state.view==='reports') await loadReport();
    render(); updateBoard();
  } catch(error) {
    if (epoch!==state.epoch) return;
    state.loading=false; state.error=error.message; render();
    throw error;
  }
}
async function refreshProjects(preferred) {
  state.projects = await allPages('/api/projects');
  const project = state.projects.find(p=>p.id===(preferred || state.project?.id)) || state.projects[0];
  if (project) await selectProject(project.id);
  else {state.project=null;state.tasks=[];state.members=[];state.loading=false;render();}
}
async function refreshTasks() {
  const id = state.project?.id;
  if (!id) return;
  const tasks = await allPages(`/api/tasks?project_id=${id}`);
  if (id!==state.project?.id) return;
  state.tasks = tasks; state.report=null; render(); updateBoard();
  pollUnread();
}
async function loadReport() {
  const id = state.project?.id;
  if (!id) return;
  const data = await api(`/reports-api/reports/projects/${id}`);
  if (id===state.project?.id) state.report=data;
}
async function loadNotifications() {
  const page = state.notificationPage;
  const data = await api(`/notify/notifications?limit=30&offset=${page*30}`);
  if (page!==state.notificationPage) return;
  state.notifications=data; state.unread=data.unread_count;
  if (state.view==='notifications') render();
}
async function pollUnread() {
  if (!state.user) return;
  try {
    const data = await api('/notify/notifications?limit=1');
    state.unread=data.unread_count;
    for (const id of ['nav-unread','bell-unread']) {
      const badge=document.getElementById(id);
      if (badge) {badge.hidden=!state.unread;badge.textContent=state.unread;}
    }
  } catch { /* Keep the workspace usable during a notification outage. */ }
}
async function changeView(view) {
  state.view=view;state.error='';render();updateBoard();
  try {
    if (view==='notifications') await loadNotifications();
    if (view==='reports' && state.project) {await loadReport();if(state.view===view) render();}
  } catch(error) {state.error=error.message;render();}
}
function logout() {
  sessionStorage.removeItem('tracker-token');state.token=null;state.user=null;
  state.projects=[];state.project=null;state.tasks=[];state.members=[];state.notifications=null;state.unread=0;state.epoch++;
  state.notificationPage=0;state.error='';state.loading=false;
  closeModal(); renderAuth();
}
function openModal(title,body) {
  modalVersion++;
  modal.innerHTML=`<div class="modal-head"><h2 id="modal-title">${e(title)}</h2><button class="icon-btn" data-action="close-modal" aria-label="Закрыть">${icon('close')}</button></div><div class="modal-body">${body}</div>`;
  if (!modal.open) modal.showModal();
}
function closeModal() {modalVersion++;modal.close();modal.innerHTML='';}
function projectModal() {
  openModal('Новый проект',`<form id="project-form" class="stack"><div class="form-field"><label for="new-project-name">Название проекта</label><input id="new-project-name" name="name" required maxlength="150" placeholder="Например, запуск приложения" autofocus></div><div class="form-field"><label for="new-project-description">Описание</label><textarea id="new-project-description" name="description" maxlength="10000" placeholder="Какая у проекта цель?"></textarea></div><div class="form-error" role="alert"></div><div class="modal-footer"><button class="btn" type="button" data-action="close-modal">Отмена</button><button class="btn primary" type="submit">Создать проект</button></div></form>`);
}
async function taskModal(taskId=null,status='todo') {
  if (!state.project) return projectModal();
  let task={title:'',description:'',status,priority:'medium',due_date:null,assignee_id:null};
  let comments=[];
  if (taskId) {
    openModal('Открываем задачу…','<div class="loading">Загружаем детали</div>');
    const version=modalVersion;
    try {[task,comments] = await Promise.all([api(`/api/tasks/${taskId}`),allPages(`/api/tasks/${taskId}/comments`)]);}
    catch(error) {if(version===modalVersion) closeModal();throw error;}
    if(version!==modalVersion) return;
  }
  const canDelete = taskId && [task.creator_id,state.project.owner_id].includes(state.user.id);
  openModal(taskId?`Задача TSK-${taskId}`:'Новая задача',`<form id="task-form" data-task-id="${taskId||''}" class="stack">
    <div class="form-field"><label for="task-title">Название задачи</label><input id="task-title" name="title" required maxlength="200" value="${e(task.title)}" placeholder="Что нужно сделать?"></div>
    <div class="form-field"><label for="task-description">Описание</label><textarea id="task-description" name="description" maxlength="10000" placeholder="Детали, которые помогут команде">${e(task.description)}</textarea></div>
    <div class="form-grid"><div class="form-field"><label for="task-status">Статус</label><select id="task-status" name="status">${options(statuses,task.status)}</select></div><div class="form-field"><label for="task-priority">Приоритет</label><select id="task-priority" name="priority">${options(priorities,task.priority)}</select></div><div class="form-field"><label for="task-assignee">Исполнитель</label><select id="task-assignee" name="assignee_id"><option value="">Не назначен</option>${state.members.map(user=>`<option value="${user.id}" ${task.assignee_id===user.id?'selected':''}>${e(user.name)}</option>`).join('')}</select></div><div class="form-field"><label for="task-due">Срок</label><input id="task-due" name="due_date" type="date" value="${e(task.due_date||'')}"></div></div><div class="form-error" role="alert"></div><div class="modal-footer">${canDelete?'<button class="btn danger" type="button" data-delete-task="'+taskId+'">'+icon('trash')+'</button>':''}<button class="btn" type="button" data-action="close-modal">Отмена</button><button class="btn primary" type="submit">${taskId?'Сохранить':'Создать задачу'}</button></div></form>
    ${taskId?`<section class="comment-section"><h3>Обсуждение · ${comments.length}</h3><div id="comments">${comments.map(comment=>`<article class="comment">${avatar(comment.author)}<div class="grow"><div class="comment-heading"><strong>${e(comment.author.name)}</strong><time>${timeLabel(comment.created_at)}</time></div><p>${e(comment.body)}</p></div>${[comment.author_id,state.project.owner_id].includes(state.user.id)?`<button class="icon-btn" data-delete-comment="${comment.id}" data-task-id="${taskId}" aria-label="Удалить комментарий">${icon('trash')}</button>`:''}</article>`).join('') || '<p class="small muted" style="margin-top:16px">Начните обсуждение — оставьте первый комментарий.</p>'}</div><form id="comment-form" class="comment-form" data-task-id="${taskId}"><div class="grow"><label class="small muted" for="comment-body">Комментарий</label><textarea id="comment-body" name="body" required maxlength="5000" placeholder="Напишите команде…"></textarea><div class="form-error" role="alert"></div></div><button class="btn primary" type="submit" aria-label="Отправить комментарий">${icon('arrow')}</button></form></section>`:''}`);
}
function confirmModal(title,message,onConfirm) {
  openModal(title,`<p>${e(message)}</p><div class="form-error" role="alert"></div><div class="modal-footer"><button class="btn" data-action="close-modal">Отмена</button><button class="btn danger" id="confirm-action">Удалить</button></div>`);
  modal.querySelector('#confirm-action').addEventListener('click',async event=>{
    event.target.disabled=true;
    try {await onConfirm();closeModal();} catch(error) {modal.querySelector('.form-error').textContent=error.message;event.target.disabled=false;}
  });
}

async function onClick(event) {
  const target=event.target.closest('button');
  if (!target || target.disabled) return;
  try {
    if (target.dataset.view) return await changeView(target.dataset.view);
    if (target.dataset.project) {state.view='board';return await selectProject(Number(target.dataset.project));}
    if (target.dataset.task) return await taskModal(Number(target.dataset.task));
    if (target.dataset.notificationTask) {
      await post(`/notify/notifications/${target.dataset.eventId}/read`,{},'PATCH');
      state.view='board';await selectProject(Number(target.dataset.projectId));
      return await taskModal(Number(target.dataset.notificationTask));
    }
    if (target.dataset.read) {await post(`/notify/notifications/${target.dataset.read}/read`,{},'PATCH');return await loadNotifications();}
    if (target.dataset.page!==undefined) {state.notificationPage=Number(target.dataset.page);return await loadNotifications();}
    if (target.dataset.removeMember) {
      return confirmModal('Исключить участника?','Участник потеряет доступ к проекту. Его задачи останутся без исполнителя.',async()=>{
        await api(`/api/projects/${state.project.id}/members/${target.dataset.removeMember}`,{method:'DELETE'});
        await selectProject(state.project.id);toast('Участник исключён');
      });
    }
    if (target.dataset.deleteTask) return confirmModal('Удалить задачу?','Задача и её комментарии будут удалены.',async()=>{
      await api(`/api/tasks/${target.dataset.deleteTask}`,{method:'DELETE'});await refreshTasks();toast('Задача удалена');
    });
    if (target.dataset.deleteComment) {
      target.disabled=true;
      await api(`/api/tasks/${target.dataset.taskId}/comments/${target.dataset.deleteComment}`,{method:'DELETE'});
      return await taskModal(Number(target.dataset.taskId));
    }
    switch(target.dataset.action) {
      case 'auth-switch':state.authMode=state.authMode==='login'?'register':'login';renderAuth();break;
      case 'logout':logout();break;
      case 'menu':document.querySelector('#sidebar').classList.toggle('open');break;
      case 'new-project':projectModal();break;
      case 'new-task':await taskModal(null,target.dataset.status||'todo');break;
      case 'close-modal':closeModal();break;
      case 'mine':state.mine=!state.mine;target.classList.toggle('active',state.mine);updateBoard();break;
      case 'read-all':await post('/notify/notifications/read-all',{},'PATCH');await loadNotifications();toast('Все уведомления прочитаны');break;
      case 'refresh':state.error='';if(state.view==='notifications') await loadNotifications();else {await refreshProjects();if(state.view==='reports') await changeView('reports');}break;
      case 'download-report':{
        const response=await api(`/reports-api/reports/projects/${state.project.id}.csv`,{raw:true});
        const url=URL.createObjectURL(await response.blob());const link=document.createElement('a');
        link.href=url;link.download=`project-${state.project.id}.csv`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);break;
      }
      case 'delete-project':confirmModal('Удалить проект?','Все задачи, комментарии и список участников этого проекта будут удалены.',async()=>{
        await api(`/api/projects/${state.project.id}`,{method:'DELETE'});state.project=null;state.view='board';await refreshProjects();toast('Проект удалён');
      });break;
    }
  } catch(error) {toast(error.message);}
}
async function onSubmit(event) {
  const form=event.target;
  event.preventDefault();
  if (!form.checkValidity()) return form.reportValidity();
  const data=Object.fromEntries(new FormData(form));
  const submit=form.querySelector('[type="submit"]');
  const errorBox=form.querySelector('.form-error');
  if (errorBox) errorBox.textContent='';
  submit.disabled=true;
  try {
    switch(form.id) {
      case 'auth-form':{
        const result=await post(`/api/users/${state.authMode}`,data);
        state.token=result.access_token;state.user=result.user;sessionStorage.setItem('tracker-token',state.token);
        state.view='board';state.error='';await refreshProjects();await pollUnread();break;
      }
      case 'project-form':{
        const project=await post('/api/projects',data);closeModal();state.view='board';await refreshProjects(project.id);toast('Проект создан');break;
      }
      case 'project-settings':{
        await post(`/api/projects/${state.project.id}`,data,'PATCH');await refreshProjects();toast('Проект обновлён');break;
      }
      case 'member-form':await post(`/api/projects/${state.project.id}/members`,data);await selectProject(state.project.id);toast('Участник добавлен');break;
      case 'task-form':{
        data.assignee_id=data.assignee_id?Number(data.assignee_id):null;data.due_date=data.due_date||null;
        const id=form.dataset.taskId;
        if (!id) data.project_id=state.project.id;
        await post(id?`/api/tasks/${id}`:'/api/tasks',data,id?'PATCH':'POST');
        closeModal();await refreshTasks();toast(id?'Задача сохранена':'Задача создана');break;
      }
      case 'comment-form':{
        const id=Number(form.dataset.taskId);
        await post(`/api/tasks/${id}/comments`,data);await taskModal(id);pollUnread();break;
      }
    }
  } catch(error) {if(errorBox?.isConnected) errorBox.textContent=error.message;else toast(error.message);}
  finally {submit.disabled=false;}
}
app.addEventListener('click',onClick);modal.addEventListener('click',onClick);
app.addEventListener('submit',onSubmit);modal.addEventListener('submit',onSubmit);
app.addEventListener('input',event=>{if(event.target.id==='search'){state.query=event.target.value;updateBoard();}});
app.addEventListener('change',event=>{if(event.target.id==='priority-filter'){state.priority=event.target.value;updateBoard();}});
modal.addEventListener('cancel',()=>{modalVersion++;});
modal.addEventListener('click',event=>{if(event.target===modal){const bounds=modal.getBoundingClientRect();if(event.clientX<bounds.left||event.clientX>bounds.right||event.clientY<bounds.top||event.clientY>bounds.bottom) closeModal();}});
setInterval(pollUnread,20000);

(async()=>{
  if (!state.token) return renderAuth();
  try {state.user=await api('/api/users/me');await refreshProjects();await pollUnread();}
  catch(error) {if(state.user){state.error=error.message;render();}else renderAuth();toast(error.message);}
})();
