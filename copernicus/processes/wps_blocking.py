import logging
import os

from pywps import FORMATS, ComplexInput, ComplexOutput, Format, LiteralInput, LiteralOutput, Process
from pywps.app.Common import Metadata
from pywps.response.status import WPS_STATUS

from copernicus.processes.utils import default_outputs, model_experiment_ensemble

from .. import runner, util

LOGGER = logging.getLogger("PYWPS")


class Blocking(Process):
    def __init__(self):
        inputs = [
            *model_experiment_ensemble(
                models=['EC-EARTH'],
                experiments=['historical'],
                ensembles=['r2i1p1'],
                start_end_year=(1850, 2005),
                start_end_defaults=(1980, 1989)),
            LiteralInput(
                'season',
                'Season',
                abstract='Choose a season like DJF.',
                data_type='string',
                allowed_values=['DJF', 'MAM', 'JJA', 'SON', 'ALL'],
                default='DJF'),
        ]
        outputs = [
            *default_outputs(),
            ComplexOutput(
                'tm90_plot',
                'Output plot',
                abstract='Generated output plot of ESMValTool processing.',
                as_reference=True,
                supported_formats=[Format('image/png')]),
            ComplexOutput(
                'blocking_plot',
                'Blocking Events Frequency Plot',
                abstract='Generated output plot of ESMValTool processing.',
                as_reference=True,
                supported_formats=[Format('image/png')]),
            ComplexOutput(
                'archive',
                'Archive',
                abstract=
                'The complete output of the ESMValTool processing as an zip archive.',
                as_reference=True,
                supported_formats=[Format('application/zip')]),
        ]

        super(Blocking, self).__init__(
            self._handler,
            identifier="blocking",
            title="Run the blocking R scripts",
            version=runner.VERSION,
            abstract="Run the blocking R scripts",
            metadata=[
                Metadata('ESMValTool', 'http://www.esmvaltool.org/'),
                Metadata(
                    'Documentation',
                    'https://copernicus-wps-demo.readthedocs.io/en/latest/processes.html#pydemo',
                    role=util.WPS_ROLE_DOC),
                Metadata(
                    'Media',
                    util.diagdata_url() + '/pydemo/pydemo_thumbnail.png',
                    role=util.WPS_ROLE_MEDIA),
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
            ensemble=request.inputs['ensemble'][0].data,
        )

        options = dict(season=request.inputs['season'][0].data)

        # generate recipe
        response.update_status("generate recipe ...", 10)
        start_year = request.inputs['start_year'][0].data
        end_year = request.inputs['end_year'][0].data
        recipe_file, config_file = runner.generate_recipe(
            workdir=self.workdir,
            diag='miles_blocking',
            constraints=constraints,
            options=options,
            start_year=start_year,
            end_year=end_year,
            output_format='png',
        )

        # recipe output
        response.outputs['recipe'].output_format = FORMATS.TEXT
        response.outputs['recipe'].file = recipe_file

        # run diag
        response.update_status("running diagnostic ...", 20)
        result = runner.run(recipe_file, config_file)
        logfile = result['logfile']
        workdir = result['work_dir']

        response.outputs['success'].data = result['success']

        # log output
        response.outputs['log'].output_format = FORMATS.TEXT
        response.outputs['log'].file = logfile

        # debug log output
        response.outputs['debug_log'].output_format = FORMATS.TEXT
        response.outputs['debug_log'].file = result['debug_logfile']

        if not result['success']:
            LOGGER.exception('esmvaltool failed!')
            response.update_status("exception occured: " + result['exception'],
                                   100)
            return response

        subdir = os.path.join(constraints['model'], constraints['experiment'],
                              constraints['ensemble'],
                              "{}_{}".format(start_year, end_year),
                              options['seasons'], 'Block')
        try:
            # result plot
            response.update_status("collecting output ...", 80)
            response.outputs['tm90_plot'].output_format = Format('application/png')
            response.outputs['tm90_plot'].file = runner.get_output(
                result['plot_dir'],
                path_filter=os.path.join('miles_diagnostics', 'miles_block',
                                        subdir),
                name_filter="TM90*",
                output_format="png")

            response.outputs['blocking_plot'].output_format = Format(
                'application/png')
            response.outputs['blocking_plot'].file = runner.get_output(
                result['plot_dir'],
                path_filter=os.path.join('miles_diagnostics', 'miles_block',
                                        subdir),
                name_filter="BlockEvents*",
                output_format="png")

            response.update_status("creating archive of diagnostic result ...", 90)

            response.outputs['archive'].output_format = Format('application/zip')
            response.outputs['archive'].file = runner.compress_output(
                os.path.join(self.workdir, 'output'), 'diagnostic_result.zip')
        except Exception as e:
            response.update_status("exception occured: " + str(e),
                                   100)
            return response

        response.update_status("done.", 100)
        return response
