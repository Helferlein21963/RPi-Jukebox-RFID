// Views of the library, in the order of the buttons. The first one is shown if none was chosen yet
const VIEWS = ['folders', 'albums', 'songs'];

const STORAGE_KEY = 'libraryLastListView';

// The view chosen last, so that the library opens with it again. Storage can be unavailable (private mode)
const loadLastView = () => {
  try {
    const view = localStorage.getItem(STORAGE_KEY);
    return VIEWS.includes(view) ? view : VIEWS[0];
  } catch (e) {
    return VIEWS[0];
  }
};

const saveLastView = (view) => {
  try {
    localStorage.setItem(STORAGE_KEY, view);
  } catch (e) {
    // Then the library opens with the first view next time
  }
};

export {
  loadLastView,
  saveLastView,
  VIEWS,
};
