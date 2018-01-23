var tilestrata = require('tilestrata');
var disk = require('tilestrata-disk');
var strata = tilestrata();
var multimapnik = require('./multimapnik.js')

strata.layer('contours')
  .route('*.png')
  .use(multimapnik());

strata.listen(8099);
