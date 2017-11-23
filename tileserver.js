var tilestrata = require('tilestrata');
var disk = require('tilestrata-disk');
var mapnik = require('tilestrata-mapnik');
var strata = tilestrata();

// define layers
strata.layer('contours')
    .route('*.png')
//    .use(disk.cache({dir: 'tiles'}))
    .use(mapnik({
        pathname: 'contours.xml',
        tileSize: 256,
        scale: 1
    }));

strata.layer('peaks')
    .route('*.png')
    .use(mapnik({
        pathname: 'peaks.xml',
        tileSize: 256,
        scale: 1
    }));

// start accepting requests
strata.listen(8099);
