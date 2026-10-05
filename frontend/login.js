const API_BASE = `${window.location.origin === 'null' ? 'http://localhost:8000' : ''}/api/v1`;
const SESSION_KEY = 'cipherpay-session';

const form = document.getElementById('login-form');
const submitButton = document.getElementById('login-submit');
const errorMessage = document.getElementById('login-error');
const emailInput = document.getElementById('email');
const passwordInput = document.getElementById('password');
const title = document.getElementById('login-title');
const subtitle = document.querySelector('.login-form-subtitle');
const accountSwitch = document.getElementById('account-switch');
const registerToggle = document.getElementById('register-toggle');
let isRegistering = false;

if (sessionStorage.getItem(SESSION_KEY)) {
  window.location.replace('/dashboard');
}

document.getElementById('demo-login').addEventListener('click', () => {
  emailInput.value = 'demo@cipherpay.local';
  passwordInput.value = 'demo123';
  errorMessage.textContent = '';
  passwordInput.focus();
});

document.getElementById('password-toggle').addEventListener('click', (event) => {
  const button = event.currentTarget;
  const isVisible = passwordInput.type === 'text';
  passwordInput.type = isVisible ? 'password' : 'text';
  button.textContent = isVisible ? 'Show' : 'Hide';
  button.setAttribute('aria-label', isVisible ? 'Show password' : 'Hide password');
});

registerToggle.addEventListener('click', () => {
  isRegistering = !isRegistering;
  document.querySelector('.demo-divider').hidden = isRegistering;
  document.querySelector('.demo-access').hidden = isRegistering;
  document.querySelector('.login-form-wrap > .section-kicker').textContent = isRegistering
    ? 'GET STARTED'
    : 'WELCOME BACK';
  title.textContent = isRegistering ? 'Create your account' : 'Sign in to your workspace';
  subtitle.textContent = isRegistering
    ? 'Create a user account to review your own transaction activity.'
    : 'Enter your credentials to continue.';
  submitButton.querySelector('span').textContent = isRegistering ? 'Create account' : 'Sign in';
  accountSwitch.firstChild.textContent = isRegistering ? 'Already have an account? ' : 'Need an account? ';
  registerToggle.textContent = isRegistering ? 'Sign in instead' : 'Create a user account';
  passwordInput.minLength = isRegistering ? 8 : 1;
  errorMessage.textContent = '';
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  submitButton.disabled = true;
  submitButton.querySelector('span').textContent = isRegistering ? 'Creating account…' : 'Signing in…';
  errorMessage.textContent = '';

  try {
    const response = await fetch(`${API_BASE}/auth/${isRegistering ? 'register' : 'login'}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: emailInput.value.trim(),
        password: passwordInput.value,
      }),
    });
    let data;

    try {
      data = await response.json();
    } catch {
      throw new Error('The server returned an invalid response.');
    }

    if (!response.ok) {
      throw new Error(typeof data.detail === 'string' ? data.detail : 'Sign-in failed. Please try again.');
    }

    sessionStorage.setItem(SESSION_KEY, JSON.stringify(data));
    window.location.assign('/dashboard');
  } catch (error) {
    errorMessage.textContent = error.message === 'Failed to fetch'
      ? 'Unable to connect. Check that the CipherPay server is running.'
      : error.message;
    submitButton.disabled = false;
    submitButton.querySelector('span').textContent = isRegistering ? 'Create account' : 'Sign in';
  }
});
