"""
Despliegue del modelo en AWS SageMaker (plataforma AIaaS exigida por la EFT).

Usa SageMaker Serverless Inference: se cobra por invocación, no por hora encendida,
así que no genera costo mientras nadie lo usa. Si la cuenta no permite serverless,
usar --instancia ml.t2.medium (cobra por hora: ELIMINAR al terminar).

Requisitos:
  pip install -r requirements-sagemaker.txt
  Credenciales AWS configuradas (aws configure, o las de AWS Academy Learner Lab)
  Un rol IAM con permisos de SageMaker. En AWS Academy: arn:aws:iam::<cuenta>:role/LabRole

Uso (desde la raíz del proyecto):
  python sagemaker/deploy_sagemaker.py desplegar --rol arn:aws:iam::123456789012:role/LabRole
  python sagemaker/deploy_sagemaker.py probar   --endpoint reco-als-v20260921-052859
  python sagemaker/deploy_sagemaker.py eliminar --endpoint reco-als-v20260921-052859
"""
import argparse
import os
import shutil
import sys
import tarfile
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from core import Recommender, default_model_root, resolve_current  # noqa: E402


def empaquetar(model_dir, destino):
    """model.tar.gz con factors.npz y meta.json en la raíz (formato que espera SageMaker)."""
    path = os.path.join(destino, "model.tar.gz")
    with tarfile.open(path, "w:gz") as tar:
        for f in ("factors.npz", "meta.json"):
            tar.add(os.path.join(model_dir, f), arcname=f)
    return path


def codigo_fuente(destino):
    """Carpeta con inference.py + core.py: SageMaker la copia al contenedor."""
    src = os.path.join(destino, "code")
    os.makedirs(src)
    shutil.copy(os.path.join(ROOT, "sagemaker", "inference.py"), src)
    shutil.copy(os.path.join(ROOT, "src", "core.py"), src)
    return src


def desplegar(args):
    import sagemaker
    from sagemaker.deserializers import JSONDeserializer
    from sagemaker.serializers import JSONSerializer
    from sagemaker.serverless import ServerlessInferenceConfig
    from sagemaker.sklearn.model import SKLearnModel

    model_dir = resolve_current(default_model_root())
    version = Recommender(model_dir).version
    endpoint = args.endpoint or f"reco-als-{version}".lower()
    session = sagemaker.Session()

    with tempfile.TemporaryDirectory() as tmp:
        tar = empaquetar(model_dir, tmp)
        print(f"Subiendo {tar} a S3 (bucket {session.default_bucket()})...")
        s3_uri = session.upload_data(tar, key_prefix=f"reco/modelos/{version}")
        print(f"  -> {s3_uri}")

        model = SKLearnModel(
            model_data=s3_uri,
            role=args.rol,
            entry_point="inference.py",
            source_dir=codigo_fuente(tmp),
            framework_version="1.2-1",
            py_version="py3",
            sagemaker_session=session,
        )

        print(f"Creando endpoint '{endpoint}' (tarda 5-10 minutos)...")
        if args.instancia:
            predictor = model.deploy(initial_instance_count=1, instance_type=args.instancia,
                                     endpoint_name=endpoint,
                                     serializer=JSONSerializer(), deserializer=JSONDeserializer())
            print("\nATENCION: endpoint con instancia dedicada. Cobra por hora aunque no se use.")
        else:
            predictor = model.deploy(
                serverless_inference_config=ServerlessInferenceConfig(memory_size_in_mb=2048, max_concurrency=5),
                endpoint_name=endpoint, serializer=JSONSerializer(), deserializer=JSONDeserializer(),
            )

    print(f"\nEndpoint listo: {endpoint}")
    probar_endpoint(predictor, Recommender(model_dir))
    print(f"\nPara eliminarlo:  python sagemaker/deploy_sagemaker.py eliminar --endpoint {endpoint}")


def probar_endpoint(predictor, rec):
    import time
    usuario = next(iter(rec.uidx))
    for uid, etiqueta in ((usuario, "usuario conocido"), (999999999999, "usuario nuevo")):
        t0 = time.perf_counter()
        r = predictor.predict({"user_id": str(uid), "k": 5})
        ms = (time.perf_counter() - t0) * 1000
        print(f"  {etiqueta:<17} source={r['source']:<8} {ms:7.1f} ms  ->",
              [x["product_id"] for x in r["recommendations"]])


def probar(args):
    from sagemaker.deserializers import JSONDeserializer
    from sagemaker.predictor import Predictor
    from sagemaker.serializers import JSONSerializer

    predictor = Predictor(args.endpoint, serializer=JSONSerializer(), deserializer=JSONDeserializer())
    probar_endpoint(predictor, Recommender(resolve_current(default_model_root())))


def eliminar(args):
    from sagemaker.predictor import Predictor

    predictor = Predictor(args.endpoint)
    try:
        predictor.delete_model()
    except Exception as e:  # el modelo puede haberse borrado antes
        print(f"  (modelo: {e})")
    predictor.delete_endpoint(delete_endpoint_config=True)
    print(f"Endpoint '{args.endpoint}' eliminado.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("desplegar")
    d.add_argument("--rol", required=True, help="ARN del rol IAM con permisos de SageMaker")
    d.add_argument("--endpoint", help="nombre del endpoint (por defecto reco-als-<version>)")
    d.add_argument("--instancia", help="ej. ml.t2.medium; si se omite se usa serverless")
    for nombre in ("probar", "eliminar"):
        s = sub.add_parser(nombre)
        s.add_argument("--endpoint", required=True)
    args = ap.parse_args()
    {"desplegar": desplegar, "probar": probar, "eliminar": eliminar}[args.cmd](args)
