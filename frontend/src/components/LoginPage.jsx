import React from 'react';
import AdminLoginPage from './AdminLoginPage';

/**
 * LoginPage - Backward-compatible redirect wrapper to AdminLoginPage
 * Ensures all login routes share the centered, unified FestivalFlow AI login interface.
 */
function LoginPage(props) {
  return <AdminLoginPage {...props} />;
}

export default LoginPage;
