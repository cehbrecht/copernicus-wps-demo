import os

from pywps import Process
from pywps import LiteralInput, LiteralOutput
from pywps import ComplexInput, ComplexOutput
from pywps import Format, FORMATS
from pywps.app.Common import Metadata

from copernicus import runner

import logging
LOGGER = logging.getLogger("PYWPS")


class Perfmetrics(Process):
    def __init__(self):
        inputs = [
            LiteralInput('model', 'Model',
                         abstract='Choose a model like MPI-ESM-LR.',
                         data_type='string',
                         allowed_values=['MPI-ESM-LR', 'MPI-ESM-MR'],
                         default='MPI-ESM-LR'),
            LiteralInput('experiment', 'Experiment',
                         abstract='Choose an experiment like historical.',
                         data_type='string',
                         allowed_values=['historical', 'rcp26', 'rcp45', 'rcp85'],
                         default='historical'),
            LiteralInput('ensemble', 'Ensemble',
                         abstract='Choose an ensemble like r1i1p1.',
                         data_type='string',
                         allowed_values=['r1i1p1', 'r2i1p1', 'r3i1p1'],
                         default='r1i1p1'),
            LiteralInput('start_year', 'Start year', data_type='integer',
                         abstract='Start year of model data.',
                         default="2000"),
            LiteralInput('end_year', 'End year', data_type='integer',
                         abstract='End year of model data.',
                         default="2001"),
        ]
        outputs = [
            ComplexOutput('namelist', 'namelist',
                          abstract='ESMValTool namelist used for processing.',
                          as_reference=True,
                          supported_formats=[Format('text/plain')]),
            ComplexOutput('log', 'Log File',
                          abstract='Log File of ESMValTool processing.',
                          as_reference=True,
                          supported_formats=[Format('text/plain')]),
            ComplexOutput('output', 'Output plot',
                          abstract='Generated output plot of ESMValTool processing.',
                          as_reference=True,
                          supported_formats=[Format('application/pdf')]),
        ]

        super(Perfmetrics, self).__init__(
            self._handler,
            identifier="perfmetrics",
            title="Performance metrics",
            version=runner.VERSION,
            abstract="Creates a performance metrics report comparing models using ESMValTool. "
            " The goal is to create a standard namelist for the calculation of performance metrics to quantify "
            " the ability of the models to reproduce the climatological mean annual cycle for selected "
            " Essential Climate Variables (ECVs) plus some additional corresponding diagnostics "
            " and plots to better understand and interpret the results. "
            " The namelist can be used to calculate performance metrics at different vertical "
            " levels (e.g., 5, 30, 200, 850 hPa as in Gleckler et al., 2008) and in four "
            " regions (global, tropics 20°N-20°S, northern extratropics 20°-90°N, southern extratropics 20°-90°S). "
            " As an additional reference, we consider the Righi et al. (2015) paper.",
            metadata=[
                Metadata('ESMValTool', 'http://www.esmvaltool.org/'),
                Metadata('Diagnostic Description', 'https://raw.githubusercontent.com/c3s-magic/c3s-magic-frontend/master/src/static/diagnosticsdata/perfmetrics/perfmetrics.yml'),  # noqa
                Metadata('Description', 'https://raw.githubusercontent.com/c3s-magic/c3s-magic-frontend/master/src/static/diagnosticsdata/perfmetrics/description.md'),  # noqa
                Metadata('Media', 'https://github.com/c3s-magic/c3s-magic-frontend/blob/master/src/static/diagnosticsdata/perfmetrics/Portait.png'),  # noqa
            ],
            inputs=inputs,
            outputs=outputs,
            status_supported=True,
            store_supported=True)

    def _handler(self, request, response):
        response.update_status("starting ...", 0)

        # build esgf search constraints
        constraints = dict(
            model=request.inputs['model'][0].data,
            experiment=request.inputs['experiment'][0].data,
            time_frequency='mon',
            cmor_table='Amon',
            ensemble=request.inputs['ensemble'][0].data,
        )

        # generate namelist
        response.update_status("generate namelist ...", 10)
        namelist_file, config_file = runner.generate_namelist(
            diag='perfmetrics',
            constraints=constraints,
            start_year=request.inputs['start_year'][0].data,
            end_year=request.inputs['end_year'][0].data,
            output_format='pdf',
            workdir=self.workdir,
        )

        # run diag
        response.update_status("running diag ...", 20)
        logfile, output_dir = runner.run(namelist_file, config_file)

        # namelist output
        response.outputs['namelist'].output_format = FORMATS.TEXT
        response.outputs['namelist'].file = namelist_file

        # log output
        response.outputs['log'].output_format = FORMATS.TEXT
        response.outputs['log'].file = logfile

        # result plot
        response.update_status("collect output plot ...", 90)
        response.outputs['output'].output_format = Format('application/pdf')
        response.outputs['output'].file = runner.get_output(
            output_dir,
            path_filter=os.path.join('ta850', 'cycle'),
            name_filter="ta_cycle_monthlyclim__Glob",
            output_format="pdf")
        response.update_status("done.", 100)
        return response
