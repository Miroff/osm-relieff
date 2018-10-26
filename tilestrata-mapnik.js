var mapnik = require('mapnik');
var path = require('path');
//var fs = require('fs');
var genericPool = require('generic-pool');

mapnik.register_datasource(path.join(mapnik.settings.paths.input_plugins, 'geojson.input'));

module.exports = function(options) {
  var pool;


  function initialize(server, callback) {
    console.log("init Pool");
    pool = genericPool.createPool({
      create: function(callback) {
        console.log("create Map");

        return new Promise(function(resolve, reject) {
          var map = new mapnik.Map(options.tileSize, options.tileSize);
          map.load(options.pathname, function(err) {
            if (err) reject(err);
            console.log("Map initialized");
            resolve(map);
          });
        });
      },
      destroy: function(map) {
        delete map;
      }
    }, {max: options.poolSize || process.env.UV_THREADPOOL_SIZE || require('os').cpus().length});
    callback();
  }

/* Move to separate file*/
  var EARTH_RADIUS = 6378137;
  var EARTH_DIAMETER = EARTH_RADIUS * 2;
  var EARTH_CIRCUMFERENCE = EARTH_DIAMETER * Math.PI;
  var MAX_RES = EARTH_CIRCUMFERENCE / 256;
  var ORIGIN_SHIFT = EARTH_CIRCUMFERENCE/2;

  function calculateMetatile(z, x, y, options) {
    var total = 1 << z;
    var resolution = MAX_RES / total;

    // Make sure we start at a metatile boundary.

    // Make sure we don't calculcate a metatile that is larger than the bounds.
    var metaWidth  = Math.min(1, total, total - x);
    var metaHeight = Math.min(1, total, total - y);

    // Generate all tile coordinates that are within the metatile.
    var tiles = [];
    for (var dx = 0; dx < metaWidth; dx++) {
        for (var dy = 0; dy < metaHeight; dy++) {
            tiles.push([ z, x + dx, y + dy ]);
        }
    }

    var minx = (x * 256) * resolution - ORIGIN_SHIFT;
    var miny = -((y + metaHeight) * 256) * resolution + ORIGIN_SHIFT;
    var maxx = ((x + metaWidth) * 256) * resolution - ORIGIN_SHIFT;
    var maxy = -((y * 256) * resolution - ORIGIN_SHIFT);
    return {
        width: metaWidth * options.tileSize,
        height: metaHeight * options.tileSize,
        x: x, y: y,
        tiles: tiles,
        bbox: [ minx, miny, maxx, maxy ]
    };
  }

  async function renderTile(z, x, y, format, callback) {
    var meta = calculateMetatile(z, x, y, {
      tileSize: options.tileSize,
      format: format
    });

    var headers = { 'Content-Type': 'image/png' };

    options.x = meta.x;
    options.y = meta.y;
    options.variables = { zoom: options.z };

    var map = await pool.acquire();

    map.resize(meta.width, meta.height);
    map.extent = meta.bbox;

    var image = new mapnik.Image(meta.width, meta.height);
    map.render(image, options, function(err, image) {
      process.nextTick(function() {
        // Release after the .render() callback returned
        // to avoid mapnik errors.
        pool.release(map);
      });

      if (err) throw err;
      var view = image.view(0, 0, options.tileSize, options.tileSize);
      view.encode('png', function(err, encoded) {
        if (err) throw err;
        callback(null, encoded, headers);
      });
    });
  }

  function serveImage(server, req, callback) {
    renderTile(req.z, req.x, req.y, 'png', function(err, buffer, headers) {
			if (err) {
        return callback(err);
      }

			callback(err, buffer, headers);
		});
  }

  function serveGrid(server, req, callback) {
    throw "Operation no supported";
  }

  function destroy() {
    delete mapnik;
  }


  return {
    name: 'mapnik',
    init: initialize,
    serve: options.interactivity ? serveGrid : serveImage,
    destroy: destroy
  };
};
