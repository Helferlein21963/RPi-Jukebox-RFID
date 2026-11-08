import React from 'react';
import {
  Navigate,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom';

import LibraryLists from './lists';
import { loadLastView } from './views';

const Library = () => {
  const { search: urlSearch } = useLocation();
  // The library opens with the view chosen last
  const lastListView = `${loadLastView()}${urlSearch}`;

  return (
    <Routes>
      <Route
        index
        element={<Navigate to={lastListView} replace />}
        exact
      />
      <Route
        path="*"
        element={<LibraryLists />}
      />
    </Routes>
  );
};

export default Library;
