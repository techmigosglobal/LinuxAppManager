const menuToggle = document.querySelector('.menu-toggle');
const siteNav = document.querySelector('#site-nav');

if (menuToggle && siteNav) {
  menuToggle.addEventListener('click', () => {
    const open = siteNav.classList.toggle('is-open');
    menuToggle.setAttribute('aria-expanded', String(open));
  });

  siteNav.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      siteNav.classList.remove('is-open');
      menuToggle.setAttribute('aria-expanded', 'false');
    });
  });
}

const revealItems = document.querySelectorAll('.reveal');
if ('IntersectionObserver' in window) {
  const revealObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });
  revealItems.forEach((item) => revealObserver.observe(item));
} else {
  revealItems.forEach((item) => item.classList.add('is-visible'));
}

const tiltTarget = document.querySelector('[data-tilt]');
if (tiltTarget && !window.matchMedia('(prefers-reduced-motion: reduce)').matches && window.matchMedia('(pointer: fine)').matches) {
  tiltTarget.addEventListener('pointermove', (event) => {
    const box = tiltTarget.getBoundingClientRect();
    const x = (event.clientX - box.left) / box.width - 0.5;
    const y = (event.clientY - box.top) / box.height - 0.5;
    tiltTarget.style.transform = `perspective(1600px) rotateY(${x * -7}deg) rotateX(${y * 4}deg) rotateZ(${x * 1.2}deg)`;
  });
  tiltTarget.addEventListener('pointerleave', () => {
    tiltTarget.style.transform = '';
  });
}

document.querySelectorAll('.copy-command').forEach((button) => {
  button.addEventListener('click', async () => {
    const command = button.dataset.copy;
    try {
      await navigator.clipboard.writeText(command);
      const original = button.textContent;
      button.textContent = 'Copied';
      window.setTimeout(() => { button.textContent = original; }, 1400);
    } catch {
      button.textContent = 'Select manually';
    }
  });
});
