// Album URLs carry albumartist and album. A tag can be empty (song without album tag),
// but a URL segment can't. So every value gets a leading '_': an empty tag becomes '_'.
const PREFIX = '_';

const tagToUrl = (value) => encodeURIComponent(`${PREFIX}${value || ''}`);

const tagFromUrl = (param = '') => {
  // React Router may hand over the segment already decoded: a name with '%' can't be decoded twice
  let value;
  try {
    value = decodeURIComponent(param);
  } catch (e) {
    value = param;
  }
  return value.startsWith(PREFIX) ? value.slice(PREFIX.length) : value;
};

export {
  tagFromUrl,
  tagToUrl,
};
