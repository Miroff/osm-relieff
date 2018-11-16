var tilestrata = require('tilestrata');
var disk = require('tilestrata-disk');
var strata = tilestrata();
//var multimapnik = require('./multimapnik.js')
var mapnik = require('./tilestrata-mapnik.js');

strata.layer('contours')
  .route('*.png')
  //.use(multimapnik())
  .use(mapnik({
     pathname: 'mapnik-psql.xml',
     tileSize: 256,
     poolSize: 4
  }))
  .use(disk.cache({dir: './cache/relief'}));

strata.listen(8099);
