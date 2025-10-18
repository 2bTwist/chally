export function validateEmail(email: string): string | null {
  const trimmed = email.trim();
  if (!trimmed) return 'Email is required';
  
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(trimmed)) return 'Invalid email format';
  
  return null;
}

export function validateUsername(username: string): string | null {
  const trimmed = username.trim();
  if (!trimmed) return 'Username is required';
  if (trimmed.length < 3) return 'Username must be at least 3 characters';
  if (trimmed.length > 20) return 'Username must be 20 characters or less';
  if (!/^[a-zA-Z0-9_]+$/.test(trimmed)) return 'Username can only contain letters, numbers, and underscores';
  
  return null;
}

export function validatePassword(password: string): string | null {
  if (!password) return 'Password is required';
  if (password.length < 8) return 'Password must be at least 8 characters';
  if (!/[a-zA-Z]/.test(password)) return 'Password must contain at least one letter';
  if (!/[0-9]/.test(password)) return 'Password must contain at least one number';
  
  return null;
}

export function validatePasswordMatch(password: string, confirmPassword: string): string | null {
  if (password !== confirmPassword) return 'Passwords do not match';
  return null;
}
