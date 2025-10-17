module.exports = function (api) {
  api.cache(true);
  return {
    presets: [
      'babel-preset-expo',
      'react-native-css-interop/babel',
    ],
    plugins: [
      'react-native-reanimated/plugin', // must be last
    ],
  };
};
