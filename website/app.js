(function () {
  const state = {
    lang: 'en',
    data: [],
    posters: [],
    postersLoaded: false,
    participantsLoaded: false,
    allParticipants: [],       // full list from participants.json
    participantsJsonLoaded: false,
    meta: null,                // from meta.json
    setView: null,        // set by initViewTabs, used by participant links
    filteredPeriod: null, // null = show all, 'AM', or 'PM'
    filteredDay: null,    // null = show all, or day slug like 'Thursday'
  };

  const scheduleEl = document.getElementById('schedule');
  const sessionQrEl = document.getElementById('session-qr');
  const qrSectionEl = document.getElementById('qr-section');
  const loadingEl = document.getElementById('loading');
  const errorEl = document.getElementById('error');
  const postersEl = document.getElementById('posters');
  const posterLoadingEl = document.getElementById('poster-loading');
  const posterErrorEl = document.getElementById('poster-error');

  function setLanguage(lang) {
    state.lang = lang;

    document.querySelectorAll('[data-i18n-en]').forEach((el) => {
      const en = el.getAttribute('data-i18n-en') || '';
      const fr = el.getAttribute('data-i18n-fr') || en;
      el.textContent = lang === 'fr' ? fr : en;
    });

    document.querySelectorAll('.lang-btn').forEach((btn) => {
      btn.classList.toggle('active', btn.getAttribute('data-lang') === lang);
    });

    renderMeta();
    renderSchedule();
    renderPosters();
    if (state.participantsLoaded) renderParticipants();
  }

  function renderMeta() {
    const el = document.getElementById('update-time');
    if (!el || !state.meta || !state.meta.generated_at) return;
    const d = new Date(state.meta.generated_at);
    const opts = { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' };
    const locale = state.lang === 'fr' ? 'fr-CA' : 'en-CA';
    const label = state.lang === 'fr' ? 'Mis à jour : ' : 'Updated: ';
    el.textContent = label + d.toLocaleString(locale, opts);
  }

  async function loadMeta() {
    try {
      const res = await fetch('meta.json', {cache:'no-cache'});
      if (res.ok) state.meta = await res.json();
    } catch (_) {}
    renderMeta();
  }

  function parseTheme(theme) {
    if (!theme) return { en: '', fr: '' };
    const compounds = String(theme).split('//');
    const enParts = [];
    const frParts = [];
    for (const comp of compounds) {
      const parts = comp.split('|');
      if (parts.length >= 2) {
        enParts.push(parts[0].trim());
        frParts.push(parts[1].trim());
      } else {
        const v = comp.trim();
        enParts.push(v);
        frParts.push(v);
      }
    }
    return { en: enParts.join(' // '), fr: frParts.join(' // ') };
  }

  function parseFields(fieldValue) {
    if (!fieldValue) return [];

    return String(fieldValue)
      .split(';')
      .map((part) => part.trim())
      .filter(Boolean)
      .map((part) => {
        if (part.includes('|')) {
          const [en, fr] = part.split('|', 2);
          return { en: en.trim(), fr: fr.trim() };
        }
        if (/\s*-\s*/.test(part)) {
          const [en, fr] = part.split(/\s*-\s*/, 2);
          return { en: en.trim(), fr: fr.trim() };
        }
        return { en: part, fr: part };
      });
  }

  function formatFields(fieldValue, lang) {
    const fields = parseFields(fieldValue)
      .map((entry) => lang === 'fr' ? entry.fr : entry.en)
      .filter(Boolean);

    if (!fields.length) {
      return '';
    }

    const label = lang === 'fr'
      ? (fields.length === 1 ? 'Domaine' : 'Domaines')
      : (fields.length === 1 ? 'Field' : 'Fields');

    return `${label}: ${fields.join(' · ')}`;
  }

  function periodLabel(period, lang) {
    if (lang === 'fr') {
      return period === 'AM' ? 'matin' : 'après-midi';
    }
    return period === 'AM' ? 'morning' : 'afternoon';
  }

  function roomLabel(room, lang) {
    // String room codes (e.g. "A-1502") are displayed as-is
    if (typeof room === 'string') return room;
    return lang === 'fr' ? `Salle ${room}` : `Room ${room}`;
  }

  function sessionSlug(session) {
    const day = session.day_en || session.day || '';
    return `session-${slugify(day)}-${String(session.period || '').toLowerCase()}`;
  }

  function roomSessionAnchor(session, room) {
    return `${sessionSlug(session)}-room-${slugify(room.room)}`;
  }

  function roomSessionUrl(anchorId) {
    const base = window.location.href.split('#')[0];
    return `${base}#${anchorId}`;
  }

  function qrImageUrl(value) {
    return `https://api.qrserver.com/v1/create-qr-code/?size=220x220&format=png&margin=8&data=${encodeURIComponent(value)}`;
  }

  function parseHashToFilteredPeriod() {
    const hash = window.location.hash.replace('#', '');
    if (!hash || !hash.startsWith('session-')) {
      state.filteredPeriod = null;
      state.filteredDay = null;
      return;
    }

    // Parse hash like "session-wednesday-pm-room-3"
    const parts = hash.split('-');
    if (parts.length < 3) {
      state.filteredPeriod = null;
      state.filteredDay = null;
      return;
    }

    const daySlug = parts[1]; // e.g., "thursday"
    const periodStr = parts[2]; // e.g., "pm" or "am"
    state.filteredPeriod = periodStr === 'pm' ? 'PM' : 'AM';

    // Match day slug against actual day names in data
    const matchDay = state.data.find((r) => {
      const d = r.day_en || r.day || '';
      return slugify(d) === daySlug;
    });
    state.filteredDay = matchDay ? (matchDay.day_en || matchDay.day) : null;
  }

  function slugify(value) {
    return String(value || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '') || 'item';
  }

  function setExpanded(container, expanded, detailSelector, toggleSelector) {
    container.classList.toggle('expanded', expanded);
    const details = container.querySelector(detailSelector);
    const toggleIcon = container.querySelector(toggleSelector);
    if (details) details.hidden = !expanded;
    if (toggleIcon) toggleIcon.textContent = expanded ? '–' : '+';
  }

  function scrollToHashTarget(targetId) {
    if (!targetId) return;
    const target = document.getElementById(targetId);
    if (!target) return;

    const expandable = target.closest('.talk, .poster');
    if (expandable?.classList.contains('talk')) {
      setExpanded(expandable, true, '.talk-details', '.talk-toggle');
    }
    if (expandable?.classList.contains('poster')) {
      setExpanded(expandable, true, '.poster-details', '.poster-toggle');
    }

    requestAnimationFrame(() => {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  function wireAnchorLink(linkEl, targetId) {
    if (!linkEl || !targetId) return;

    linkEl.href = `#${targetId}`;
    linkEl.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (window.location.hash === `#${targetId}`) {
        scrollToHashTarget(targetId);
      } else {
        window.location.hash = targetId;
      }
    });
  }

  function attachTalkHandlers(root) {
    root.querySelectorAll('.talk').forEach((talkEl) => {
      function toggle() {
        const expanded = !talkEl.classList.contains('expanded');
        setExpanded(talkEl, expanded, '.talk-details', '.talk-toggle');
      }
      talkEl.addEventListener('click', toggle);
      talkEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          toggle();
        }
      });
    });
  }

  function attachPosterHandlers(root) {
    root.querySelectorAll('.poster').forEach((pEl) => {
      function toggle() {
        const expanded = !pEl.classList.contains('expanded');
        setExpanded(pEl, expanded, '.poster-details', '.poster-toggle');
      }
      pEl.addEventListener('click', toggle);
      pEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          toggle();
        }
      });
    });
  }

  function renderSchedule() {
    if (!state.data || !state.data.length) return;
    scheduleEl.innerHTML = '';

    const sessionTmpl = document.getElementById('session-template');
    const roomTmpl = document.getElementById('room-template');
    const talkTmpl = document.getElementById('talk-template');

    // Filter sessions by day+period if set (e.g., from QR hash)
    const sessionsToRender = (state.filteredPeriod || state.filteredDay)
      ? state.data.filter((s) => {
          const day = s.day_en || s.day || '';
          if (state.filteredDay && day !== state.filteredDay) return false;
          if (state.filteredPeriod && s.period !== state.filteredPeriod) return false;
          return true;
        })
      : state.data;

    sessionsToRender.forEach((session) => {
      const sNode = sessionTmpl.content.cloneNode(true);
      const sEl = sNode.querySelector('.session');
      const dayEl = sNode.querySelector('.session-day');
      const periodEl = sNode.querySelector('.session-period');
      const roomsEl = sNode.querySelector('.session-rooms');

      const dayText = state.lang === 'fr' ? session.day_fr : session.day_en;
      sEl.id = sessionSlug(session);
      dayEl.textContent = dayText;
      periodEl.textContent = ` · ${periodLabel(session.period, state.lang)}`;

      session.rooms.forEach((room) => {
        const rNode = roomTmpl.content.cloneNode(true);
        const rEl = rNode.querySelector('.room-card');
        const rTitle = rNode.querySelector('.room-title');
        const rTheme = rNode.querySelector('.room-theme');
        const rInv = rNode.querySelector('.room-invited');
        const rBody = rNode.querySelector('.room-body');
        const roomAnchor = roomSessionAnchor(session, room);

        rEl.id = roomAnchor;
        rTitle.textContent = roomLabel(room.room, state.lang);
        const themeParts = parseTheme(room.theme);
        rTheme.textContent = state.lang === 'fr' ? themeParts.fr : themeParts.en;

        if (room.invited_speaker) {
          const min = room.invited_minutes || 30;
          const hasDetails = room.invited_bio || room.invited_abstract;
          const fr = state.lang === 'fr';

          // Header row
          const invHeader = document.createElement('div');
          invHeader.className = 'invited-header';

          const invLabel = document.createElement('span');
          invLabel.className = 'invited-label';
          invLabel.textContent = fr
            ? `Conférencier·ère invité·e : ${room.invited_speaker} (${min} min)`
            : `Invited speaker: ${room.invited_speaker} (${min} min)`;
          invHeader.appendChild(invLabel);

          if (hasDetails) {
            const invToggle = document.createElement('span');
            invToggle.className = 'invited-toggle';
            invToggle.textContent = '+';
            invHeader.appendChild(invToggle);
          }
          rInv.appendChild(invHeader);

          if (hasDetails) {
            const invDetails = document.createElement('div');
            invDetails.className = 'invited-details';
            invDetails.hidden = true;

            if (room.invited_title) {
              const tEl = document.createElement('div');
              tEl.className = 'invited-talk-title';
              tEl.textContent = room.invited_title;
              invDetails.appendChild(tEl);
            }

            if (room.invited_bio) {
              const lbl = document.createElement('div');
              lbl.className = 'invited-section-label';
              lbl.textContent = fr ? 'Biographie' : 'Biography';
              invDetails.appendChild(lbl);
              const bioEl = document.createElement('div');
              bioEl.className = 'invited-bio';
              bioEl.textContent = room.invited_bio;
              invDetails.appendChild(bioEl);
            }

            if (room.invited_abstract) {
              const lbl = document.createElement('div');
              lbl.className = 'invited-section-label';
              lbl.textContent = fr ? 'Résumé' : 'Abstract';
              invDetails.appendChild(lbl);
              const absEl = document.createElement('div');
              absEl.className = 'invited-abstract';
              absEl.textContent = room.invited_abstract;
              invDetails.appendChild(absEl);
            }

            rInv.appendChild(invDetails);
            rInv.setAttribute('role', 'button');
            rInv.setAttribute('tabindex', '0');
            rInv.style.cursor = 'pointer';

            const toggleInv = () => {
              const exp = !rInv.classList.contains('expanded');
              rInv.classList.toggle('expanded', exp);
              invDetails.hidden = !exp;
              const tog = rInv.querySelector('.invited-toggle');
              if (tog) tog.textContent = exp ? '–' : '+';
            };
            rInv.addEventListener('click', toggleInv);
            rInv.addEventListener('keydown', (e) => {
              if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleInv(); }
            });
          }

          rInv.hidden = false;
        } else {
          rInv.hidden = true;
        }

        room.talks.forEach((talk, idx) => {
          const tNode = talkTmpl.content.cloneNode(true);
          const tEl = tNode.querySelector('.talk');
          const slotEl = tNode.querySelector('.talk-slot');
          const titleEl = tNode.querySelector('.talk-title-link');
          const speakerEl = tNode.querySelector('.talk-speaker');
          const fieldEl = tNode.querySelector('.talk-field');
          const absEl = tNode.querySelector('.talk-abstract');
          const abstractLabelEl = tNode.querySelector('.talk-abstract-label');
          const backLinkEl = tNode.querySelector('.talk-back-link');

          const anchorBase = talk.id != null && talk.id !== ''
            ? `talk-${talk.id}`
            : `talk-${slugify(`${session.day_en}-${session.period}-${room.room}-${idx + 1}-${talk.title}`)}`;
          const titleId = `${anchorBase}-title`;
          const abstractId = `${anchorBase}-abstract`;

          slotEl.textContent = String(idx + 1).padStart(2, '0');
          titleEl.textContent = talk.title || '(no title)';
          titleEl.id = titleId;
          const name = `${talk.first || ''} ${talk.last || ''}`.trim();
          speakerEl.textContent = name ? name : '';
          fieldEl.textContent = formatFields(talk.field, state.lang);
          absEl.textContent = talk.abstract || '';
          absEl.id = abstractId;
          abstractLabelEl.textContent = state.lang === 'fr' ? 'Résumé' : 'Abstract';
          backLinkEl.textContent = state.lang === 'fr' ? 'Retour au titre' : 'Back to title';

          wireAnchorLink(titleEl, abstractId);
          wireAnchorLink(backLinkEl, titleId);

          rBody.appendChild(tNode);
        });

        roomsEl.appendChild(rNode);
      });

      scheduleEl.appendChild(sNode);
    });

    attachTalkHandlers(scheduleEl);
    renderSessionQRCodes();
    scrollToHashTarget(window.location.hash.slice(1));
  }

  function renderSessionQRCodes() {
    if (!state.data || !state.data.length) {
      qrSectionEl.hidden = true;
      sessionQrEl.innerHTML = '';
      return;
    }

    qrSectionEl.hidden = false;
    sessionQrEl.innerHTML = '';

    // Filter sessions by day+period if set
    const sessionsToRender = (state.filteredPeriod || state.filteredDay)
      ? state.data.filter((s) => {
          const day = s.day_en || s.day || '';
          if (state.filteredDay && day !== state.filteredDay) return false;
          if (state.filteredPeriod && s.period !== state.filteredPeriod) return false;
          return true;
        })
      : state.data;

    sessionsToRender.forEach((session) => {
      const block = document.createElement('section');
      block.className = 'qr-session-block';

      const heading = document.createElement('h3');
      heading.className = 'qr-session-heading';
      const dayText = state.lang === 'fr' ? session.day_fr : session.day_en;
      heading.textContent = `${dayText} · ${periodLabel(session.period, state.lang)}`;
      block.appendChild(heading);

      const cards = document.createElement('div');
      cards.className = 'qr-grid';

      session.rooms.forEach((room) => {
        const anchor = roomSessionAnchor(session, room);
        const url = roomSessionUrl(anchor);

        const card = document.createElement('article');
        card.className = 'qr-card';

        const roomName = document.createElement('div');
        roomName.className = 'qr-room';
        roomName.textContent = roomLabel(room.room, state.lang);

        const periodName = document.createElement('div');
        periodName.className = 'qr-period';
        periodName.textContent = `${dayText} · ${periodLabel(session.period, state.lang)}`;

        const qrImg = document.createElement('img');
        qrImg.className = 'qr-image';
        qrImg.src = qrImageUrl(url);
        qrImg.alt = state.lang === 'fr'
          ? `Code QR pour ${roomLabel(room.room, state.lang)}, ${dayText} ${periodLabel(session.period, state.lang)}`
          : `QR code for ${roomLabel(room.room, state.lang)}, ${dayText} ${periodLabel(session.period, state.lang)}`;
        qrImg.loading = 'lazy';

        const link = document.createElement('a');
        link.className = 'qr-link';
        link.href = `#${anchor}`;
        link.textContent = state.lang === 'fr' ? 'Ouvrir la séance' : 'Open session';

        card.appendChild(roomName);
        card.appendChild(periodName);
        card.appendChild(qrImg);
        card.appendChild(link);
        cards.appendChild(card);
      });

      block.appendChild(cards);
      sessionQrEl.appendChild(block);
    });
  }

  function renderPosters() {
    if (!state.posters || !state.posters.length) {
      postersEl.innerHTML = '';
      return;
    }

    postersEl.innerHTML = '';
    const tmpl = document.getElementById('poster-template');

    state.posters.forEach((p) => {
      const node = tmpl.content.cloneNode(true);
      const el = node.querySelector('.poster');
      const titleEl = node.querySelector('.poster-title-link');
      const speakerEl = node.querySelector('.poster-speaker');
      const fieldEl = node.querySelector('.poster-field');
      const gradeEl = node.querySelector('.poster-grade');
      const absEl = node.querySelector('.poster-abstract');
      const abstractLabelEl = node.querySelector('.poster-abstract-label');
      const backLinkEl = node.querySelector('.poster-back-link');

      const anchorBase = p.id != null && p.id !== ''
        ? `poster-${p.id}`
        : `poster-${slugify(`${p.last}-${p.title}`)}`;
      const titleId = `${anchorBase}-title`;
      const abstractId = `${anchorBase}-abstract`;

      titleEl.textContent = p.title || '(no title)';
      titleEl.id = titleId;
      const name = `${p.first || ''} ${p.last || ''}`.trim();
      speakerEl.textContent = name || '';
      fieldEl.textContent = formatFields(p.field, state.lang);
      if (p.total_grade != null && p.total_grade !== '' && !Number.isNaN(p.total_grade)) {
        const n = p.n_gradings || 0;
        if (state.lang === 'fr') {
          gradeEl.textContent = `Note moyenne: ${p.total_grade}  ·  ${n} évaluation(s)`;
        } else {
          gradeEl.textContent = `Average grade: ${p.total_grade}  ·  ${n} grading(s)`;
        }
      } else {
        gradeEl.textContent = '';
      }
      absEl.textContent = p.abstract || '';
      absEl.id = abstractId;
      abstractLabelEl.textContent = state.lang === 'fr' ? 'Résumé' : 'Abstract';
      backLinkEl.textContent = state.lang === 'fr' ? 'Retour au titre' : 'Back to title';

      wireAnchorLink(titleEl, abstractId);
      wireAnchorLink(backLinkEl, titleId);

      postersEl.appendChild(node);
    });

    attachPosterHandlers(postersEl);
    scrollToHashTarget(window.location.hash.slice(1));
  }

  function initLanguageToggle() {
    document.getElementById('lang-en').addEventListener('click', () => setLanguage('en'));
    document.getElementById('lang-fr').addEventListener('click', () => setLanguage('fr'));
  }

  function initViewTabs() {
    const oralView = document.getElementById('oral-view');
    const posterView = document.getElementById('poster-view');
    const participantView = document.getElementById('participant-view');

    function setView(view) {
      document.querySelectorAll('.view-btn').forEach((btn) => {
        btn.classList.toggle('active', btn.getAttribute('data-view') === view);
      });
      oralView.hidden = view !== 'oral';
      posterView.hidden = view !== 'posters';
      participantView.hidden = view !== 'participants';
      if (view === 'posters' && !state.postersLoaded) {
        loadPosters();
      }
      if (view === 'participants') {
        loadParticipants();
      }
    }

    state.setView = setView;

    document.getElementById('view-oral').addEventListener('click', () => setView('oral'));
    document.getElementById('view-posters').addEventListener('click', () => setView('posters'));
    document.getElementById('view-participants').addEventListener('click', () => setView('participants'));

    setView('oral');
  }

  async function loadOral() {
    try {
      const res = await fetch('schedule.json', {cache:'no-cache'});
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      state.data = data;
      loadingEl.hidden = true;
      parseHashToFilteredPeriod();
      renderSchedule();
    } catch (err) {
      console.error(err);
      loadingEl.hidden = true;
      errorEl.hidden = false;
      errorEl.textContent =
        state.lang === 'fr'
          ? "Erreur lors du chargement de l’horaire."
          : 'Error loading schedule.';
    }
  }

  async function loadPosters() {
    try {
      const res = await fetch('posters.json', {cache:'no-cache'});
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      state.posters = data;
      state.postersLoaded = true;
      posterLoadingEl.hidden = true;
      renderPosters();
    } catch (err) {
      console.error(err);
      posterLoadingEl.hidden = true;
      posterErrorEl.hidden = false;
      posterErrorEl.textContent =
        state.lang === 'fr'
          ? "Erreur lors du chargement des affiches."
          : 'Error loading posters.';
    }
  }

  function buildParticipants() {
    const map = new Map();

    function key(first, last) {
      return `${(last || '').toLowerCase()}|||${(first || '').toLowerCase()}`;
    }

    function getOrCreate(first, last) {
      const k = key(first, last);
      if (!map.has(k)) {
        map.set(k, { first: (first || '').trim(), last: (last || '').trim(), talks: [], posters: [] });
      }
      return map.get(k);
    }

    // Start with the full registered participants list (participants.json)
    state.allParticipants.forEach((p) => {
      getOrCreate(p.first, p.last);
    });

    // Add talk links from oral schedule
    state.data.forEach((session) => {
      session.rooms.forEach((room) => {
        if (room.invited_speaker) {
          const parts = room.invited_speaker.trim().split(/\s+/);
          if (parts.length >= 2) {
            const last = parts[parts.length - 1];
            const first = parts.slice(0, -1).join(' ');
            getOrCreate(first, last);
          } else if (parts.length === 1) {
            getOrCreate('', parts[0]);
          }
        }
        room.talks.forEach((talk) => {
          if (talk.first || talk.last) {
            const p = getOrCreate(talk.first, talk.last);
            if (talk.id != null && talk.id !== '') p.talks.push(talk.id);
          }
        });
      });
    });

    // Add poster links
    state.posters.forEach((poster) => {
      if (poster.first || poster.last) {
        const p = getOrCreate(poster.first, poster.last);
        if (poster.id != null && poster.id !== '') p.posters.push(poster.id);
      }
    });

    return [...map.values()].sort((a, b) => {
      const lc = a.last.localeCompare(b.last, undefined, { sensitivity: 'base' });
      return lc !== 0 ? lc : a.first.localeCompare(b.first, undefined, { sensitivity: 'base' });
    });
  }

  function renderParticipants() {
    const container = document.getElementById('participants');
    if (!container) return;
    container.innerHTML = '';

    const participants = buildParticipants();

    if (!participants.length) {
      const msg = document.createElement('p');
      msg.className = 'status';
      msg.textContent = state.lang === 'fr' ? 'Aucun participant.' : 'No participants found.';
      container.appendChild(msg);
      return;
    }

    const totalEl = document.createElement('p');
    totalEl.className = 'participant-total';
    const total = participants.length;
    totalEl.textContent = state.lang === 'fr'
      ? `${total} participant${total > 1 ? 's' : ''}`
      : `${total} participant${total > 1 ? 's' : ''}`;
    container.appendChild(totalEl);

    let currentLetter = '';
    let letterGroup = null;
    let list = null;

    participants.forEach((p) => {
      const rawLetter = p.last[0] || '#';
      const letter = rawLetter.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase();

      if (letter !== currentLetter) {
        currentLetter = letter;
        letterGroup = document.createElement('div');
        letterGroup.className = 'participant-letter-group';

        const heading = document.createElement('h3');
        heading.className = 'participant-letter';
        heading.textContent = letter;
        letterGroup.appendChild(heading);

        list = document.createElement('ul');
        list.className = 'participant-list';
        letterGroup.appendChild(list);
        container.appendChild(letterGroup);
      }

      const li = document.createElement('li');
      li.className = 'participant-entry';

      const nameSpan = document.createElement('span');
      nameSpan.className = 'participant-name';
      nameSpan.textContent = p.first ? `${p.last}, ${p.first}` : p.last;
      li.appendChild(nameSpan);

      p.talks.forEach((id) => {
        const link = document.createElement('a');
        link.href = `#talk-${id}-abstract`;
        link.className = 'participant-badge participant-badge-talk';
        link.textContent = state.lang === 'fr' ? 'Exposé' : 'Talk';
        link.addEventListener('click', (e) => {
          e.preventDefault();
          if (state.setView) state.setView('oral');
          window.location.hash = `talk-${id}-abstract`;
        });
        li.appendChild(link);
      });

      p.posters.forEach((id) => {
        const link = document.createElement('a');
        link.href = `#poster-${id}-abstract`;
        link.className = 'participant-badge participant-badge-poster';
        link.textContent = state.lang === 'fr' ? 'Affiche' : 'Poster';
        link.addEventListener('click', (e) => {
          e.preventDefault();
          if (state.setView) state.setView('posters');
          // Wait one tick for the poster view to render
          setTimeout(() => { window.location.hash = `poster-${id}-abstract`; }, 50);
        });
        li.appendChild(link);
      });

      list.appendChild(li);
    });
  }

  async function loadParticipants() {
    const loadingEl = document.getElementById('participant-loading');
    // Ensure both data sources are loaded
    const needsPosters = !state.postersLoaded;
    if (needsPosters) {
      try {
        const res = await fetch('posters.json', {cache:'no-cache'});
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        state.posters = data;
        state.postersLoaded = true;
      } catch (err) {
        console.error('Failed to load posters for participants:', err);
      }
    }
    if (!state.participantsJsonLoaded) {
      try {
        const res = await fetch('participants.json', {cache:'no-cache'});
        if (res.ok) {
          state.allParticipants = await res.json();
          state.participantsJsonLoaded = true;
        }
      } catch (err) {
        console.error('Failed to load participants.json:', err);
      }
    }
    if (loadingEl) loadingEl.hidden = true;
    state.participantsLoaded = true;
    renderParticipants();
  }

  initLanguageToggle();
  initViewTabs();
  setLanguage('en');
  loadMeta();
  loadOral();
  window.addEventListener('hashchange', () => {
    parseHashToFilteredPeriod();
    renderSchedule();
    scrollToHashTarget(window.location.hash.slice(1));
  });
})();
