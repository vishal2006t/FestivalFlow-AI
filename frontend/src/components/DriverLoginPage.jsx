import React from 'react';
import AdminLoginPage from './AdminLoginPage';

/**
 * DriverLoginPage - Renders the unified centered FestivalFlow AI login interface
 * defaulted to the Field Operations & Telematics (Bus Driver) role.
 */
function DriverLoginPage(props) {
  return <AdminLoginPage {...props} initialRole="driver" />;
}

export default DriverLoginPage;
