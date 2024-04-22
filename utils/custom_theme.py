from st_aggrid import JsCode
from colorsys import hsv_to_rgb, rgb_to_hsv
from st_pages import Page

def color_gradient(start_hex, finish_hex="#FFFFFF", n=10, alpha=1.0):
    """ returns a gradient list of (n) colors between
    two hex colors. start_hex and finish_hex
    should be the full six-digit color string,
    including the number sign ("#FFFFFF") """

    # Starting and ending colors in RGB form
    s = start_hex
    f = finish_hex
    # Convert hex colors to RGB
    start_rgb = tuple(int(s[i:i+2], 16) for i in (1, 3, 5))
    finish_rgb = tuple(int(f[i:i+2], 16) for i in (1, 3, 5))

    if n ==1:
        return [f"rgba({start_rgb[0]}, {start_rgb[1]}, {start_rgb[2]}, {alpha})"]
    # Convert RGB to HSV
    start_hsv = rgb_to_hsv(*start_rgb)
    finish_hsv = rgb_to_hsv(*finish_rgb)
    # Generate a list of HSV tuples between start and end
    hsv_tuples = [(start_hsv[0] + (i * (finish_hsv[0] - start_hsv[0]) / (n-1)),
                start_hsv[1] + (i * (finish_hsv[1] - start_hsv[1]) / (n-1)),
                start_hsv[2] + (i * (finish_hsv[2] - start_hsv[2]) / (n-1)))
                for i in range(n)]
    # Convert the HSV tuples to RGB tuples and scale to 0-255
    rgb_tuples = [(int(rgb[0]), int(rgb[1]), int(rgb[2])) for rgb in [hsv_to_rgb(*hsv) for hsv in hsv_tuples]]
    # Add the alpha value to the RGB tuples to create RGBA tuples
    rgba_tuples = [(rgb[0], rgb[1], rgb[2], alpha) for rgb in rgb_tuples]
    # Create a list of strings in the format "rgba(r, g, b, a)"
    return ["rgba({}, {}, {}, {})".format(rgba[0], rgba[1], rgba[2], rgba[3]) for rgba in rgba_tuples]


sale_sytle_jscode = JsCode("""
    function(params) {
        if (params.value > 0) {
            return {
                'color': 'rgb(57,158,52)',
            }
        } else if (params.value != 0) {
            return {
                'color': 'rgb(237,61,46)',
            }
        }
    };
    """)

profit_rate_sytle_jscode = JsCode("""
    function(params) {
        if (params.value > 0) {
            return {
                'color': 'rgb(57,158,52)',
            }
        } else if (params.value != 0) {
            return {
                'color': 'rgb(237,61,46)',
            }
        }
    };
    """)

staff_sytle_jscode = JsCode("""
    function(params) {
        if (params.value < 3 && params.value > 0) {
            return {
                'color': 'rgb(237,61,46)',
            }
        } else if (params.value != 0 ){
            return {
                'color': 'rgb(57,158,52)',
            }
        }
    };
    """)

norm_hour_sytle_jscode = JsCode("""
    function(params) {
        if (params.value < 90 ) {
            return {
                'color': 'rgb(237,61,46)',
            }
        } else {
            return {
                'color': 'rgb(57,158,52)',
            }
        }
    };
    """)

train_ill_hour_sytle_jscode = JsCode("""
    function(params) {
        if (params.value >= 10) {
            return {
                'color': 'rgb(237,61,46)',
            }
        } else {
            return {
                'color': 'rgb(57,158,52)',
            }
        }
    };
    """)

salmon_sytle_jscode = JsCode("""
    function(params) {
        if (params.value > 23) {
            return {
                'color': 'rgb(237,61,46)',
            }
        } else if (params.value > 0) {
            return {
                'color': 'rgb(57,158,52)',
            }
        }
    };
    """)

material_rate_sytle_jscode = JsCode("""
    function(params) {
        if (params.value > 35) {
            return {
                'color': 'rgb(237,61,46)',
            }
        } else if (params.value > 0) {
            return {
                'color': 'rgb(57,158,52)',
            }
        }
    };
    """)

staff_rate_sytle_jscode = JsCode("""
    function(params) {
        if (params.value > 35) {
            return {
                'color': 'rgb(237,61,46)',
            }
        } else if (params.value > 0) {
            return {
                'color': 'rgb(57,158,52)',
            }
        }
    };
    """)

other_rate_sytle_jscode = JsCode("""
    function(params) {
        if (params.value > 5) {
            return {
                'color': 'rgb(237,61,46)',
            }
        } else if (params.value > 0) {
            return {
                'color': 'rgb(57,158,52)',
            }
        }
    };
    """)

percent_formatter = JsCode("""
function percent_formatter(params) {
    // Check if the value is NaN
    if (isNaN(params.value)) {
        // If value is NaN, use 0
        return '';
    } else {
        // If value is not NaN, proceed as usual
        return params.value.toFixed(1) + '%';
    }
}
""")

decimal_formatter = JsCode("""
function decimal_formatter(params) {
    // Check if the value is NaN
    if (isNaN(params.value)) {
        // If value is NaN, use 0
        return '';
    } else {
        // If value is not NaN, proceed as usual
        return params.value.toFixed(1);
    }
}
""")


int_formatter = JsCode("""function int_formatter(params) {
    return params.value.toFixed(0);
}""")

currency_formatter = JsCode("""function currency_formatter(params) {
    return '€ '+ params.value.toFixed(1);
}""")


calculateProfitRate = JsCode(
"""
function calculateProfitRate(params) {
        var salesSum = params.data['Sales €'];
        var profitSum = params.data['Profit €'];
        return salesSum;
    }
""")



customAggFunc = JsCode(
"""
function customAggFunc(params) {
    // calculate the sum of Column A
    var sumA = 0;
    params.values.forEach(function(value) {
        sumA += value;
    });

  // calculate the sum of Column B
    var sumB = 0;
    params.api.forEachLeafNode(function(node) {
        if (node.group) return;  // skip group header nodes
        if (node.field === 'Hour') {  // only process nodes of Column B
        sumB += node.data['Hour'];
        }
    });

    // return the division of Column A by Column B
    return sumB;
    }
""")


profitCalc = JsCode(
"""
function profitCalc(params) {
        if (params.data) {
            return  100*params.api.getValue('Profit €', params.node) / params.api.getValue('Sales €', params.node);
        }
    };
""")

innerRenderer = JsCode(
"""
function(params) {
          if (params.node.group) {  // only perform calculation for group header rows
            var salesSum = params.api.getValue('Sales €', params.node);
            var profitSum = params.api.getValue('Profit €', params.node);
            return (profitSum / salesSum).toFixed(2);  // returns profit rate for group, rounded to 2 decimal places
          } else {  // for normal rows, return the original 'profitRate' value
            return params.value;
        }
        }
""")


custom_css = {
    ".ag-theme-streamlit": {
        "--ag-alpine-active-color": "#006ee6 !important",
        "--ag-range-selection-border-color": "#006ee6 !important",
        "--ag-odd-row-background-color": "#fafafa !important",
        "--ag-row-hover-color": "rgba(0,193,203,0.1) !important",
        "--ag-input-focus-border-color": "rgba(0,110,230,.4)",
        },
    }

