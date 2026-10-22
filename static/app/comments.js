document.addEventListener('click', (event) => {
  if (!(event.target instanceof Element)) return;
  const opener = event.target.closest('[data-comments-open]');
  if (!opener) return;

  const dialog = document.getElementById(opener.dataset.commentsOpen);
  if (dialog instanceof HTMLDialogElement && !dialog.open) dialog.showModal();
});

document.addEventListener('click', (event) => {
  const dialog = event.target;
  if (dialog instanceof HTMLDialogElement && dialog.classList.contains('comments-dialog')) {
    const bounds = dialog.getBoundingClientRect();
    const outside = event.clientX < bounds.left || event.clientX > bounds.right
      || event.clientY < bounds.top || event.clientY > bounds.bottom;
    if (outside) dialog.close();
  }
});

const commentHash = window.location.hash.match(/^#comments-(\d+)$/);
if (commentHash) {
  const dialog = document.getElementById(`comments-dialog-${commentHash[1]}`);
  if (dialog instanceof HTMLDialogElement) dialog.showModal();
}

const notificationCenter = document.querySelector('.notification-center');
if (notificationCenter instanceof HTMLElement) {
  const toggle = notificationCenter.querySelector('.notification-toggle');
  const panel = notificationCenter.querySelector('.notifications-panel');
  const list = notificationCenter.querySelector('.notification-list');
  const badge = notificationCenter.querySelector('.notification-badge');
  const feedUrl = notificationCenter.dataset.notificationFeed;
  const readTemplate = notificationCenter.dataset.notificationReadTemplate;
  const csrfCookie = document.cookie.split('; ').find((part) => part.startsWith('csrftoken='));
  const csrfToken = csrfCookie ? csrfCookie.split('=')[1] : '';

  if (
    toggle instanceof HTMLButtonElement
    && panel instanceof HTMLElement
    && list instanceof HTMLUListElement
    && badge instanceof HTMLSpanElement
    && feedUrl
    && readTemplate
  ) {
    function updateBadge(count) {
      badge.textContent = count > 99 ? '99+' : String(count);
      badge.hidden = count === 0;
      toggle.setAttribute('aria-label', count ? `Bildirishnomalar (${count} ta yangi)` : 'Bildirishnomalar');
    }

    function describeNotification(notification) {
      const labels = {
        like: 'postingizni yoqtirdi',
        comment: 'postingizga komment yozdi',
        follow: 'sizga obuna bo‘ldi',
        message: 'sizga xabar yubordi',
      };
      return labels[notification.kind] || 'sizga bildirishnoma yubordi';
    }

    function renderNotifications(notifications) {
      list.replaceChildren();
      if (notifications.length === 0) {
        const empty = document.createElement('li');
        empty.className = 'notification-empty';
        empty.textContent = 'Hozircha bildirishnoma yo‘q.';
        list.append(empty);
        return;
      }

      notifications.forEach((notification) => {
        const item = document.createElement('li');
        item.className = `notification-item${notification.is_read ? '' : ' is-unread'}`;
        const link = document.createElement('a');
        link.className = 'notification-link';
        link.href = notification.url;

        const copy = document.createElement('span');
        copy.className = 'notification-copy';
        const actor = document.createElement('strong');
        actor.textContent = notification.actor;
        copy.append(actor, ` ${describeNotification(notification)}`);

        const time = document.createElement('time');
        time.className = 'notification-time';
        time.textContent = notification.created_at;
        link.append(copy, time);

        if (!notification.is_read) {
          const dot = document.createElement('span');
          dot.className = 'notification-unread-dot';
          dot.setAttribute('aria-label', 'O‘qilmagan');
          link.append(dot);
        }
        item.append(link);
        item.dataset.notificationId = String(notification.id);
        item.dataset.read = String(notification.is_read);
        list.append(item);
      });
    }

    async function refreshNotifications() {
      const response = await fetch(feedUrl, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
      });
      if (!response.ok) throw new Error(`Bildirishnomalarni yuklab bo‘lmadi (${response.status})`);
      const data = await response.json();
      renderNotifications(data.notifications);
      updateBadge(data.unread_count);
    }

    toggle.addEventListener('click', () => {
      const open = panel.hidden;
      panel.hidden = !open;
      toggle.setAttribute('aria-expanded', String(open));
    });

    list.addEventListener('click', async (event) => {
      if (!(event.target instanceof Element)) return;
      const link = event.target.closest('.notification-link');
      const item = link?.closest('.notification-item');
      if (!(link instanceof HTMLAnchorElement) || !(item instanceof HTMLLIElement)) return;
      if (item.dataset.read === 'true') return;

      event.preventDefault();
      const url = link.href;
      const notificationId = item.dataset.notificationId;
      if (!notificationId) return;
      try {
        const response = await fetch(readTemplate.replace('/0/read/', `/${notificationId}/read/`), {
          method: 'POST',
          headers: {
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest',
          },
          credentials: 'same-origin',
        });
        if (!response.ok) throw new Error(`Bildirishnomani o‘qilgan deb belgilab bo‘lmadi (${response.status})`);
        const data = await response.json();
        item.dataset.read = 'true';
        item.classList.remove('is-unread');
        item.querySelector('.notification-unread-dot')?.remove();
        updateBadge(data.unread_count);
        window.location.assign(url);
      } catch (error) {
        console.error(error);
      }
    });

    document.addEventListener('click', (event) => {
      if (!(event.target instanceof Node) || notificationCenter.contains(event.target)) return;
      panel.hidden = true;
      toggle.setAttribute('aria-expanded', 'false');
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        panel.hidden = true;
        toggle.setAttribute('aria-expanded', 'false');
      }
    });

    refreshNotifications().catch((error) => console.error(error));
    window.setInterval(() => {
      refreshNotifications().catch((error) => console.error(error));
    }, 10000);
  }
}
