var mapnik = require('tilestrata-mapnik');
var mapnikNative = require('mapnik');
var SphericalMercator = require('@mapbox/sphericalmercator');
var async = require("async");
var fs = require('fs');

var renderers = [];
var sm = new SphericalMercator({ size: 256 });

function find_renderers(bbox) {
  var result = [];
  for (var i = 0; i < renderers.length; i++) {
    var r = renderers[i];
    if (r.bbox[0] > bbox[2] || r.bbox[2] < bbox[0] || r.bbox[1] > bbox[3] || r.bbox[3] < bbox[1]) {
      continue;
    }
    result.push(r);
  }
  return result;
}

function init_renderers(server, callback) {
  fs.readdir('mapnik-config', function(err, files) {
    for (var i = 0; i < files.length; i++) {
      var g = files[i].match(/N(\d{2})E(\d{3}).xml/);
      if (!g) {
        continue;
      }

      var lat = parseInt(g[1]), lon = parseInt(g[2]);

      var bbox = [lon, lat, lon + 1, lat + 1];

      var renderer = mapnik({
          pathname: 'mapnik-config/' + g[0],
          tileSize: 256,
          scale: 1
      });

      renderers.push({bbox: bbox, renderer});
    }

    async.map(renderers, function (r, callback) {
      callback(null, function(cb) {
        r.renderer.init(server, function(err) {
          cb(err);
        });
      });
    }, function(err, functions) {
      async.series(functions, function(err) {
        console.log('initialization complete');
        callback(err);
      });
    });
  });
}


function serve(bbox, tile, callback) {
  var rs = find_renderers(bbox);

  if (rs.length == 0) {
    return callback("renderers not found for bbox " + bbox);
  }

  async.map(rs, function(r, callback) {
    r.renderer.serve(null, tile, function(err, buffer, headers) {
      mapnikNative.Image.fromBytes(buffer, function(err, image) {
        image.premultiply(function (err) {
          callback(err, image);
        });
      });
    })
  }, function(err, images) {
    if (err) return callback(err);

    var intermediate = new mapnikNative.Image(256, 256);
    intermediate.premultiply(function (err, intermediate) {
      if (err) {
        return callback(err);
      }

      async.reduce(images, intermediate, function(memo, image, cb) {
          memo.composite(image, function(err, image) {
            cb(null, image);
          });
        }, function(err, memo) {
          if (err) {
            return callback(err);
          }

          memo.demultiply(function (err, memo) {
            memo.encode('png', function(err, buffer) {
              if (err) {
                return callback(err);
              }

            callback(null, buffer, {'Content-Type': 'image/png'});
          });
        })
      });
    });
  })
}

module.exports = function() {
  return {
    name: 'multimapnik',
    init: function(server, callback) {
      init_renderers(server, callback);
    },

    serve: function(server, tile, callback) {
      var bbox = sm.bbox(tile.x, tile.y, tile.z);

      serve(bbox, tile, callback);
    },
    destroy: function(server, callback) {
      //TODO: Destroy renderers
      callback(null);
    }
  }
}
