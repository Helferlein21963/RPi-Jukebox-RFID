// Album URLs carry albumartist and album. A tag can be empty (song without album tag),
// but a URL segment can't. MPD tags never contain line breaks, so a line break stands for an empty tag.
const EMPTY_TAG = '\n';

const tagToUrl = (value) => encodeURIComponent(value || EMPTY_TAG);

const tagFromUrl = (param = '') => {
  const value = decodeURIComponent(param);
  return value === EMPTY_TAG ? '' : value;
};

export {
  tagFromUrl,
  tagToUrl,
};
